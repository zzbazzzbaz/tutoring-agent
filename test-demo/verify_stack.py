"""验证全链路：LangGraph 1.x + AsyncPostgresSaver + DashScope + pgvector"""

import asyncio
import uuid
from typing import Optional
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import interrupt, Command
from pydantic import BaseModel, Field


# ── 1. DashScope LLM 接入 ──────────────────────────────
API_KEY = "sk-cad2e2400e384fc7aa08846770dac9e1"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

llm = ChatOpenAI(
    model="qwen3.5-flash",
    api_key=API_KEY,
    base_url=BASE_URL,
    temperature=0.7,
    extra_body={"enable_thinking": False},
)

embedder = OpenAIEmbeddings(
    model="text-embedding-v4",
    api_key=API_KEY,
    base_url=BASE_URL,
    check_embedding_ctx_length=False,
)


# ── 2. 结构化输出测试 ──────────────────────────────────
class SentimentResult(BaseModel):
    sentiment: str = Field(description="positive/negative/neutral")
    reason: str = Field(description="判断理由")


async def test_structured_output():
    """测试 with_structured_output（function calling 模式）"""
    structured_llm = llm.with_structured_output(SentimentResult, method="function_calling")
    result = await structured_llm.ainvoke("今天考试考了满分，太开心了！")
    print(f"[结构化输出] sentiment={result.sentiment}, reason={result.reason}")
    assert result.sentiment == "positive"
    print("[结构化输出] PASS")


# ── 3. Embedding 测试 ──────────────────────────────────
async def test_embedding():
    vec = await embedder.aembed_query("TCP三次握手")
    print(f"[Embedding] dim={len(vec)}")
    assert len(vec) == 1024
    print("[Embedding] PASS")


# ── 4. LangGraph interrupt/resume + AsyncPostgresSaver ─
DB_URL = "postgresql://root:guoqitong123456@101.35.223.219:15433/root"

class GraphState(TypedDict):
    messages: list[str]
    quiz_answer: Optional[str]
    verdict: Optional[str]


async def ask_node(state: GraphState):
    """出题节点：interrupt 等待用户答题"""
    user_msg = state["messages"][-1]
    # 模拟出题
    answer = interrupt({"question": "TCP三次握手的第二步是什么？", "context": user_msg})
    return {"quiz_answer": answer}


async def eval_node(state: GraphState):
    """评估节点"""
    answer = state.get("quiz_answer", "")
    verdict = "correct" if "SYN" in answer.upper() or "ACK" in answer.upper() else "wrong"
    return {"verdict": verdict}


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("ask", ask_node)
    builder.add_node("eval", eval_node)
    builder.add_edge(START, "ask")
    builder.add_edge("ask", "eval")
    builder.add_edge("eval", END)
    return builder


async def test_graph():
    """测试 interrupt/resume + PostgresSaver"""
    async with AsyncPostgresSaver.from_conn_string(DB_URL) as checkpointer:
        await checkpointer.setup()
        graph = build_graph().compile(checkpointer=checkpointer)

        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        # 第一次调用：到 ask 节点会 interrupt
        result = await graph.ainvoke({"messages": ["考考我"]}, config=config)
        print(f"[Graph] interrupt 后的状态: {list(result.keys()) if result else 'empty (interrupted)'}")

        # 检查是否在 interrupt 状态
        state = await graph.aget_state(config)
        print(f"[Graph] 当前状态: next={state.next}, values={state.values}")

        # resume：提交答案
        result2 = await graph.ainvoke(Command(resume="SYN-ACK"), config=config)
        print(f"[Graph] resume 后: verdict={result2.get('verdict')}")
        assert result2.get("verdict") == "correct"
        print("[Graph] interrupt/resume + PostgresSaver PASS")


# ── 5. pgvector 存取测试 ───────────────────────────────
async def test_pgvector():
    """测试 pgvector 向量存储与检索"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(DB_URL.replace("postgresql://", "postgresql+asyncpg://"))
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE IF NOT EXISTS test_vec (id text, content text, embedding vector(1024))"))
        await conn.execute(text("DELETE FROM test_vec"))

        # 写入两条向量
        vec1 = await embedder.aembed_query("TCP三次握手")
        vec2 = await embedder.aembed_query("UDP协议特点")
        query_vec = await embedder.aembed_query("什么是TCP握手")

        await conn.execute(text("INSERT INTO test_vec VALUES (:id, :c, :e)"), {"id": "1", "c": "TCP三次握手", "e": str(vec1)})
        await conn.execute(text("INSERT INTO test_vec VALUES (:id, :c, :e)"), {"id": "2", "c": "UDP协议特点", "e": str(vec2)})

        # 检索
        result = await conn.execute(text("SELECT id, content, embedding <=> :q AS dist FROM test_vec ORDER BY dist LIMIT 1"), {"q": str(query_vec)})
        row = result.fetchone()
        print(f"[pgvector] 最相似: id={row[0]}, content={row[1]}, dist={row[2]:.4f}")
        assert row[0] == "1"
        await conn.execute(text("DROP TABLE test_vec"))
        print("[pgvector] PASS")

    await engine.dispose()


async def main():
    print("=" * 50)
    print("开始全链路验证...")
    print("=" * 50)

    await test_structured_output()
    await test_embedding()
    await test_graph()
    await test_pgvector()

    print("=" * 50)
    print("全部通过！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
