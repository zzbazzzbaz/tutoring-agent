"""Agent 工具实现：search_knowledge_base / quiz_flow / end_session。

每个工具用 make_*_tool 工厂函数创建，绑定会话上下文（session_type + session_context + session_id）。

关键设计：
- quiz_flow 用 check-before-create 幂等模式（参考 langgraph-human-in-the-loop skill）
- interrupt() 之前只做幂等操作（upsert Question），之后做非幂等操作（评估、保存答案）
- end_session 从 Message 表查对话历史，调错题整理 Agent
"""
import uuid

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent.agents.llm import get_llm, structured_call
from teaching_agent.agents.schemas import QuizOutput, EvaluationOutput, ConsolidationOutput
from teaching_agent.agents.prompts import QUIZ_PROMPT, EVALUATION_PROMPT, CONSOLIDATION_PROMPT
from teaching_agent.config import settings
from teaching_agent.db import async_session_factory
from teaching_agent.models import (
    Question, AnswerRecord, MistakeItem, StudentProfile,
    Session as SessionModel, Message, KnowledgePoint,
)
from teaching_agent.rag.retriever import graphrag_search, format_chunks
from teaching_agent.rag.graph import get_all_kp_names


# ============================================================
# search_knowledge_base
# ============================================================

def make_search_tool(session_type: str, session_context: dict):
    """创建知识库检索工具，绑定会话类型和上下文。

    Args:
        session_type: free / project / review
        session_context: 会话上下文（project_id / mistake_data 等）
    """
    @tool
    async def search_knowledge_base(query: str) -> str:
        """检索课程知识库，返回与查询相关的知识片段。

        当学生提问或讨论某个概念时，先调用此工具检索相关知识，
        再基于检索内容设计苏格拉底式追问。检索结果包含向量匹配和知识图谱扩展的片段。

        Args:
            query: 检索关键词，需包含完整上下文（消除代词指代）
        """
        async with async_session_factory() as session:
            chunks = await graphrag_search(session, query, session_type, session_context)
            return format_chunks(chunks)

    return search_knowledge_base


# ============================================================
# quiz_flow
# ============================================================

async def _get_pending_question(session: AsyncSession, session_id: str, topic: str) -> Question | None:
    """幂等检查：是否已有该 session+topic 的 pending 题目。

    interrupt() 恢复时工具会重跑，此函数确保不重复生成题目。
    """
    stmt = select(Question).where(
        Question.session_id == session_id,
        Question.status == "pending",
    )
    result = await session.execute(stmt)
    questions = result.scalars().all()
    # 按 kp_name / stem 模糊匹配 topic（LLM 生成的题可能 kp_name 不完全等于 topic）
    for q in questions:
        if topic in q.stem or topic in (q.kp_id or ""):
            return q
    # 如果只有一个 pending 题目，直接返回（常见情况）
    if len(questions) == 1:
        return questions[0]
    return None


async def _get_kp_id_by_name(session: AsyncSession, kp_name: str) -> str | None:
    """按名称查知识点 ID。"""
    stmt = select(KnowledgePoint).where(KnowledgePoint.name == kp_name)
    result = await session.execute(stmt)
    kp = result.scalar_one_or_none()
    return kp.id if kp else None


def make_quiz_tool(session_type: str, session_context: dict, session_id: str):
    """创建出题工具，绑定会话上下文。

    Args:
        session_type: free / project / review
        session_context: 会话上下文
        session_id: 会话 ID，用于 Question 落库
    """
    @tool
    async def quiz_flow(topic: str) -> str:
        """出一道关于指定知识点的题目，等待学生作答后返回评估结果。

        当学生说"考考我"、需要检验理解程度、或你判断时机成熟时调用此工具。
        调用后会暂停等待学生答题，学生提交答案后自动判分。

        Args:
            topic: 要出题的知识点名称
        """
        # --- interrupt 之前：幂等操作（check-before-create）---
        async with async_session_factory() as session:
            pending = await _get_pending_question(session, session_id, topic)

            if pending:
                # resume 路径：复用已生成的题目，不调 LLM
                quiz_data = pending
            else:
                # 首次调用：生成题目
                # 检索相关知识片段
                chunks = await graphrag_search(session, topic, session_type, session_context)
                retrieved_text = format_chunks(chunks)

                # 获取可用知识点列表
                kp_names = await get_all_kp_names(session)

                # 构建出题 prompt
                review_context = ""
                variant_requirement = ""
                if session_type == "review" and "mistake_data" in session_context:
                    mistake = session_context["mistake_data"]
                    if isinstance(mistake, dict):
                        orig = mistake.get("title", "")
                    else:
                        orig = getattr(mistake, "title", "")
                    review_context = f"原题：{orig}\n出变式题：同知识点，不同考法、不同角度。"
                    variant_requirement = "出变式题，不能与原题考法相同。"

                prompt = QUIZ_PROMPT.format(
                    course_name=settings.COURSE_NAME,
                    topic=topic,
                    conversation_context=f"会话类型: {session_type}",
                    retrieved_chunks=retrieved_text,
                    weak_points="无",
                    available_kps=", ".join(kp_names) if kp_names else "（暂无）",
                    review_context=review_context,
                    variant_requirement=variant_requirement,
                )

                try:
                    quiz_output: QuizOutput = await structured_call(
                        get_llm(), QuizOutput, prompt
                    )
                except Exception as e:
                    return f"出题失败，继续对话。错误: {e}"

                # 查知识点 ID（可能不存在，用名称匹配）
                kp_id = await _get_kp_id_by_name(session, quiz_output.kp_name)

                # upsert Question（幂等：同一 session+topic 只创建一次）
                quiz_data = Question(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    kp_id=kp_id,
                    q_type=quiz_output.q_type,
                    stem=quiz_output.stem,
                    options=quiz_output.options,
                    answer=quiz_output.answer,
                    analysis=quiz_output.analysis,
                    source_chunk_ids=quiz_output.source_chunk_ids,
                    status="pending",
                )
                session.add(quiz_data)
                await session.commit()
                await session.refresh(quiz_data)

            # --- interrupt：暂停等待学生答题 ---
            # 首次调用 raise（暂停）；resume 时返回学生答案
            student_answer = interrupt({
                "question_id": quiz_data.id,
                "q_type": quiz_data.q_type,
                "stem": quiz_data.stem,
                "options": quiz_data.options,
            })

            # --- interrupt 之后：非幂等操作（只执行一次）---
            # 处理跳过
            if isinstance(student_answer, dict) and student_answer.get("action") == "skip":
                quiz_data.status = "skipped"
                session.add(quiz_data)
                await session.commit()
                return "学生跳过了本题"

            # 提取答案文本
            if isinstance(student_answer, dict):
                answer_text = student_answer.get("answer", "")
            else:
                answer_text = str(student_answer)

            # 评估 Agent 判分
            eval_prompt = EVALUATION_PROMPT.format(
                question_stem=quiz_data.stem,
                q_type=quiz_data.q_type,
                correct_answer=quiz_data.answer,
                student_answer=answer_text,
                kp_name=quiz_data.kp_id or topic,
                retrieved_chunks="（依据题目标准答案评判）",
            )

            try:
                eval_result: EvaluationOutput = await structured_call(
                    get_llm(), EvaluationOutput, eval_prompt
                )
            except Exception as e:
                return f"评判异常，请重新提交。错误: {e}"

            # 保存答题记录（非幂等，只执行一次）
            async with async_session_factory() as eval_session:
                record = AnswerRecord(
                    id=str(uuid.uuid4()),
                    question_id=quiz_data.id,
                    user_id="demo-student",
                    session_id=session_id,
                    user_answer=answer_text,
                    verdict=eval_result.verdict,
                    diagnosis=eval_result.diagnosis,
                )
                eval_session.add(record)

                # 更新题目状态
                quiz_data.status = "answered"
                eval_session.add(quiz_data)
                await eval_session.commit()

            return (
                f"判定: {eval_result.verdict}\n"
                f"错因: {eval_result.diagnosis}\n"
                f"正确答案: {eval_result.correct_answer}\n"
                f"后续方向: {eval_result.follow_up_hint}"
            )

    return quiz_flow


# ============================================================
# end_session
# ============================================================

async def _get_session_messages(session_id: str) -> tuple[str, str]:
    """从 Message 表获取会话对话历史和答题记录。

    Returns:
        (full_conversation, answer_records) 文本
    """
    async with async_session_factory() as session:
        # 查所有消息
        msg_stmt = select(Message).where(
            Message.session_id == session_id
        ).order_by(Message.created_at)
        result = await session.execute(msg_stmt)
        messages = result.scalars().all()

        conversation_lines = []
        for m in messages:
            role = "学生" if m.role == "user" else "老师"
            conversation_lines.append(f"{role}: {m.content}")
        full_conversation = "\n".join(conversation_lines) if conversation_lines else "（无对话记录）"

        # 查答题记录
        ar_stmt = select(AnswerRecord, Question).join(
            Question, AnswerRecord.question_id == Question.id
        ).where(AnswerRecord.session_id == session_id)
        ar_result = await session.execute(ar_stmt)
        ar_rows = ar_result.all()

        record_lines = []
        for record, question in ar_rows:
            record_lines.append(
                f"题目: {question.stem} | 学生答: {record.user_answer} | 判定: {record.verdict}"
            )
        answer_records = "\n".join(record_lines) if record_lines else "（无答题记录）"

    return full_conversation, answer_records


async def _save_mistakes(
    session: AsyncSession,
    mistakes: list,
    source_session_id: str,
) -> None:
    """保存错题（去重合并：question_id 已存在则更新）。"""
    for m in mistakes:
        # 查是否有同 question_id 的错题
        if m.question_id:
            stmt = select(MistakeItem).where(
                MistakeItem.question_id == m.question_id,
                MistakeItem.user_id == "demo-student",
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                # 更新原记录，重置掌握状态
                existing.wrong_answer = m.wrong_answer
                existing.correct_answer = m.correct_answer
                existing.diagnosis = m.diagnosis
                existing.mastery_status = "unmastered"
                session.add(existing)
                continue

        # 按 kp_name 查 kp_id
        kp_id = None
        if m.kp_name:
            kp_stmt = select(KnowledgePoint).where(KnowledgePoint.name == m.kp_name)
            kp_result = await session.execute(kp_stmt)
            kp = kp_result.scalar_one_or_none()
            if kp:
                kp_id = kp.id

        # 新建错题
        session.add(MistakeItem(
            id=str(uuid.uuid4()),
            user_id="demo-student",
            question_id=m.question_id,
            kp_id=kp_id,
            title=m.title,
            wrong_answer=m.wrong_answer,
            correct_answer=m.correct_answer,
            diagnosis=m.diagnosis,
            source_chunk_ids=m.source_chunk_ids,
            mastery_status="unmastered",
            source_session_id=source_session_id,
        ))


async def _update_profile(
    session: AsyncSession,
    profile_summary: str,
    weak_points: list[str],
) -> None:
    """更新学生画像（增量）。"""
    stmt = select(StudentProfile).where(StudentProfile.user_id == "demo-student")
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile:
        profile.summary = profile_summary
        # weak_points 转为 [{kp_name, score, misconception}] 格式
        profile.weak_points = [
            {"kp_name": wp, "score": 0.5, "misconception": ""}
            for wp in weak_points
        ]
        session.add(profile)
    else:
        session.add(StudentProfile(
            id=str(uuid.uuid4()),
            user_id="demo-student",
            summary=profile_summary,
            weak_points=[
                {"kp_name": wp, "score": 0.5, "misconception": ""}
                for wp in weak_points
            ],
            learning_style="未知",
        ))


def make_end_session_tool(session_type: str, session_context: dict, session_id: str):
    """创建结束会话工具，绑定会话上下文。

    Args:
        session_type: free / project / review
        session_context: 会话上下文
        session_id: 会话 ID
    """
    @tool
    async def end_session() -> str:
        """结束当前学习会话，自动整理错题并更新学生画像。

        当学生说"结束"、"再见"、"不学了"或明确要求结束时调用。
        调用后会回顾全程对话，提炼错题加入错题本，更新画像和知识点掌握度。
        """
        # 获取对话历史和答题记录
        full_conversation, answer_records = await _get_session_messages(session_id)

        # 获取旧画像
        async with async_session_factory() as session:
            stmt = select(StudentProfile).where(StudentProfile.user_id == "demo-student")
            result = await session.execute(stmt)
            profile = result.scalar_one_or_none()
            old_summary = profile.summary if profile else "新学生"
            old_weak = (
                [wp.get("kp_name", str(wp)) for wp in profile.weak_points]
                if profile and profile.weak_points
                else []
            )

        # 调错题整理 Agent
        prompt = CONSOLIDATION_PROMPT.format(
            full_conversation=full_conversation,
            answer_records=answer_records,
            old_profile_summary=old_summary,
            old_weak_points=", ".join(old_weak) if old_weak else "无",
        )

        try:
            consolidation: ConsolidationOutput = await structured_call(
                get_llm(), ConsolidationOutput, prompt
            )
        except Exception as e:
            return f"会话结束，但错题整理失败: {e}"

        # 落库
        async with async_session_factory() as session:
            # 保存错题
            await _save_mistakes(session, consolidation.mistakes, session_id)

            # 更新画像
            await _update_profile(session, consolidation.profile_summary, consolidation.weak_points)

            # review 会话额外更新错题掌握状态
            if session_type == "review" and "mistake_id" in session_context:
                mistake_id = session_context["mistake_id"]
                mistake = await session.get(MistakeItem, mistake_id)
                if mistake:
                    # 查本会话所有答题记录
                    ar_stmt = select(AnswerRecord).where(
                        AnswerRecord.session_id == session_id
                    )
                    ar_rows = (await session.execute(ar_stmt)).scalars().all()
                    # 全部答对 -> mastered，否则 reviewing
                    if ar_rows and all(r.verdict == "correct" for r in ar_rows):
                        mistake.mastery_status = "mastered"
                    else:
                        mistake.mastery_status = "reviewing"
                    session.add(mistake)

            # 更新会话标题和摘要
            sess = await session.get(SessionModel, session_id)
            if sess:
                sess.title = consolidation.title
                sess.summary = consolidation.summary
                sess.status = "ended"
                from datetime import datetime, timezone
                sess.ended_at = datetime.now(timezone.utc)
                session.add(sess)

            await session.commit()

        return f"会话已结束。{consolidation.summary}"

    return end_session
