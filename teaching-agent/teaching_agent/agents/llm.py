"""LLM 与 Embedder 工厂函数 + 统一结构化调用。"""
import asyncio

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from teaching_agent.config import settings


def get_llm() -> ChatOpenAI:
    """获取对话 LLM 实例（DashScope OpenAI 兼容端点）。

    qwen3.6-flash 是 thinking 模型，必须关闭 enable_thinking 否则
    with_structured_output 的 tool_choice=required 会报 400 错误。
    """
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
        temperature=0.7,
        extra_body={"enable_thinking": False},
    )


def get_embedder() -> OpenAIEmbeddings:
    """获取向量化模型实例。

    check_embedding_ctx_length=False 是因为 DashScope 不接受 tiktoken
    分词后的 token ID，只接受原始文本。
    """
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
        check_embedding_ctx_length=False,
    )


async def structured_call(llm, schema, prompt, max_retries: int = 2):
    """统一结构化调用：with_structured_output + 指数退避重试。

    Args:
        llm: ChatOpenAI 实例
        schema: Pydantic BaseModel 类（结构化输出 schema）
        prompt: 输入 prompt 字符串
        max_retries: 最大重试次数

    Returns:
        schema 实例

    Raises:
        最后一次重试仍失败时抛出原始异常
    """
    structured = llm.with_structured_output(schema, method="function_calling")
    for i in range(max_retries + 1):
        try:
            return await structured.ainvoke(prompt)
        except Exception:
            if i == max_retries:
                raise
            await asyncio.sleep(2 ** i)
    return None
