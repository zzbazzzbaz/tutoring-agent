# 平时分--AI 评分服务
# 复用 analytics/summary.py 的 httpx 直连 DashScope 模式；只喂聚合指标，不喂对话原文
import json
import logging
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.analytics.schemas import ScoringResultResponse, StudentScoreItem
from tutoring.core.config import settings
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.db.models import Class, StudentScore

logger = logging.getLogger(__name__)

# 占位符判断与 analytics/summary.py 同口径
_PLACEHOLDER_SUBSTR = "你的阿里云"

DEFAULT_SCORING_PROMPT = """\
你是一名课程助教，请根据每位学生在本课程教学系统中的使用数据，为学生评定平时分（满分 100 分）。

评分维度参考（可自行调整权重与细则）：
1. 使用频率与持续性（40 分）：会话数、活跃天数、最近活跃时间；
2. 互动投入度（30 分）：学生主动发起的消息数量、提问与追问情况；
3. 知识运用与项目推进（30 分）：知识库命中率、项目学习阶段完成与产出物达标情况。

评分要求：
- 横向对比全班学生，保持评分标准一致；
- 完全没有使用记录的学生应低于 60 分；
- 拉开区分度，避免集中在同一分数；
- 每人为 0-100 的整数分。"""

_SYSTEM_PROMPT = """\
你是一名课程评分助手。请严格按照教师给出的评分标准，为每位学生评定 0-100 的整数平时分，\
并给出 30 字以内的简短理由（中文）。
输出必须是 JSON 数组，格式为：[{"index": 1, "score": 85, "reason": "理由"}]
- index 为学生数据表中的行号，必须与输入一一对应，不得遗漏或重复。
- 只输出 JSON 本体，不要输出任何其他内容。"""


class ScoringUnavailable(Exception):
    """AI 评分不可用：未配置 key / LLM 异常 / 解析失败。"""


def _key_available() -> bool:
    """是否配置了可用的 DashScope API Key（与 summary.py 同口径）。"""
    key = settings.dashscope_api_key
    if key is None:
        return False
    raw = key.get_secret_value().strip()
    return bool(raw) and raw.isascii() and _PLACEHOLDER_SUBSTR not in raw


def _build_metrics(row: dict, proj: dict) -> dict:
    """学生指标快照（落库 + 响应）。"""
    msg = row["student_messages"]
    return {
        "sessions": row["sessions"],
        "student_messages": msg,
        "active_days": row["active_days"],
        "knowledge_hits": row["knowledge_hits"],
        "knowledge_hit_rate": round(row["knowledge_hits"] / msg, 4) if msg else 0.0,
        "project_sessions": proj.get("project_sessions", 0),
        "stages_completed": proj.get("stages_completed", 0),
        "stages_total": proj.get("stages_total", 0),
        "deliverables_done": proj.get("deliverables_done", 0),
        "deliverables_total": proj.get("deliverables_total", 0),
        "last_active_at": row["last_active_at"].isoformat() if row["last_active_at"] else None,
    }


def _render_usage_table(rows: list[dict], project_stats: dict[UUID, dict]) -> str:
    """渲染学生指标数据表（行号 | 姓名 | ...），喂给 LLM。"""
    header = (
        "行号 | 姓名 | 会话数 | 学生消息数 | 活跃天数 | 知识命中率 | "
        "项目会话 | 阶段完成 | 产出物达标 | 最近活跃"
    )
    lines = [header]
    for i, row in enumerate(rows, start=1):
        proj = project_stats.get(row["user_id"], {})
        msg = row["student_messages"]
        rate = f"{round(row['knowledge_hits'] / msg * 100)}%" if msg else "-"
        last = row["last_active_at"].strftime("%Y-%m-%d") if row["last_active_at"] else "-"
        lines.append(
            f"{i} | {row['name']} | {row['sessions']} | {msg} | {row['active_days']} | {rate} | "
            f"{proj.get('project_sessions', 0)} | "
            f"{proj.get('stages_completed', 0)}/{proj.get('stages_total', 0)} | "
            f"{proj.get('deliverables_done', 0)}/{proj.get('deliverables_total', 0)} | {last}"
        )
    return "\n".join(lines)


def _build_user_prompt(teacher_prompt: str, table: str, since: date | None) -> str:
    scope = f"{since.isoformat()} 至今日" if since else "全部历史"
    return f"【评分标准】\n{teacher_prompt}\n\n【学生使用数据】（统计范围：{scope}）\n{table}"


async def _call_llm(user_prompt: str) -> str:
    """调用 DashScope（OpenAI 兼容），返回 content 文本。"""
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
        "stream": False,
    }
    url = f"{settings.dashscope_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""


def _extract_json_array(text: str) -> list[dict]:
    """容错提取 JSON 数组（剥围栏/前后文本）。"""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end <= start:
        raise ScoringUnavailable("AI 未返回 JSON 数组")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ScoringUnavailable("AI 返回内容无法解析为 JSON") from exc
    if not isinstance(data, list):
        raise ScoringUnavailable("AI 返回不是 JSON 数组")
    return data


def _parse_scores(text: str, rows: list[dict]) -> list[dict]:
    """解析 AI 输出并映射回 student_id；行号不完整/分数非法 → ScoringUnavailable。"""
    by_index: dict[int, dict] = {}
    for item in _extract_json_array(text):
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        if isinstance(idx, bool) or not isinstance(idx, int) or idx in by_index:
            continue
        by_index[idx] = item
    if set(by_index) != set(range(1, len(rows) + 1)):
        raise ScoringUnavailable("AI 评分结果行号不完整，请重试")

    results: list[dict] = []
    for i, row in enumerate(rows, start=1):
        item = by_index[i]
        try:
            score = int(round(float(item.get("score"))))
        except (TypeError, ValueError) as exc:
            raise ScoringUnavailable("AI 评分结果分数非法，请重试") from exc
        results.append(
            {
                "student_id": row["user_id"],
                "score": min(max(score, 0), 100),
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    return results


async def generate_scores(
    db: AsyncSession,
    teacher_id: UUID,
    class_id: UUID,
    since: date | None = None,
) -> ScoringResultResponse:
    """生成班级平时分并覆盖落库；失败抛 ScoringUnavailable（不落库）。"""
    cls = await db.get(Class, class_id)
    if (
        not cls
        or cls.teacher_id != teacher_id
        or cls.deleted_at is not None
        or cls.status != "active"
    ):
        raise AppError(404, "CLASS_NOT_FOUND", "班级不存在或不属于当前教师")

    class_name = f"{cls.grade} {cls.classname}"

    rows = await repos.list_class_student_usage(db, class_id=class_id, since=since)
    if not rows:
        await repos.replace_class_student_scores(db, class_id, [])
        return ScoringResultResponse(
            class_id=class_id, class_name=class_name, since=since, generated_at=None, items=[]
        )

    project_stats = await repos.get_class_student_project_stats(db, class_id=class_id)
    stored = await repos.get_scoring_prompt(db, teacher_id)
    teacher_prompt = stored.prompt if stored else DEFAULT_SCORING_PROMPT

    if not _key_available():
        raise ScoringUnavailable("DASHSCOPE_API_KEY 未配置或为占位符")

    table = _render_usage_table(rows, project_stats)
    user_prompt = _build_user_prompt(teacher_prompt, table, since)
    try:
        text = await _call_llm(user_prompt)
    except Exception as exc:
        logger.warning("scoring LLM request failed: %s", exc)
        raise ScoringUnavailable("LLM 评分服务异常") from exc

    scores = _parse_scores(text, rows)

    generated_at = datetime.now(ZoneInfo("Asia/Shanghai"))
    orm_rows: list[StudentScore] = []
    items: list[StudentScoreItem] = []
    for row, s in zip(rows, scores, strict=True):
        metrics = _build_metrics(row, project_stats.get(row["user_id"], {}))
        orm_rows.append(
            StudentScore(
                class_id=class_id,
                student_id=row["user_id"],
                score=s["score"],
                reason=s["reason"],
                metrics=metrics,
                since=since,
                generated_at=generated_at,
            )
        )
        items.append(
            StudentScoreItem(
                student_id=row["user_id"],
                name=row["name"],
                username=row["username"],
                score=s["score"],
                reason=s["reason"],
                metrics=metrics,
            )
        )

    await repos.replace_class_student_scores(db, class_id, orm_rows)
    items.sort(key=lambda it: it.score, reverse=True)
    return ScoringResultResponse(
        class_id=class_id,
        class_name=class_name,
        since=since,
        generated_at=generated_at,
        items=items,
    )
