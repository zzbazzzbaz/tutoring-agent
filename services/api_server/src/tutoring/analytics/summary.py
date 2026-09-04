# 统计分析--LLM 研究摘要
# httpx 直连 DashScope OpenAI 兼容接口，无新增依赖；未配置/异常时抛 SummaryUnavailable 由路由降级
import logging

import httpx

from tutoring.analytics.schemas import DashboardResponse
from tutoring.core.config import settings

logger = logging.getLogger(__name__)

# 占位符提示语（.env 示例值）；真实 key 为纯 ASCII，占位符含中文无法通过 isascii 校验
_PLACEHOLDER_SUBSTR = "你的阿里云"

_SUMMARY_SYSTEM_PROMPT = (
    "你是一名教育领域的统计分析助手。请根据给定的普通心理学班级学情统计数据，"
    "用简洁、专业、客观的中文写一段约 120~200 字的研究摘要。"
    "要点：概括互动规模与活跃情况、点出趋势特征与峰值、"
    "提及知识命中与待关注情况，并给出 1 条具体可执行的跟进建议。"
    "只使用给定数据，不得编造或外推任何数值。"
)


class SummaryUnavailable(Exception):
    """AI 摘要不可用：未配置 key / 占位符 key / LLM 调用失败。"""


def _key_available() -> bool:
    """判断是否配置了可用的 DashScope API Key。"""
    key = settings.dashscope_api_key
    if key is None:
        return False
    raw = key.get_secret_value().strip()
    if not raw:
        return False
    # 占位符通常含中文（非 ASCII）或提示语，视为未配置，避免用假 key 打真实接口
    if not raw.isascii() or _PLACEHOLDER_SUBSTR in raw:
        return False
    return True


def _build_user_prompt(dashboard: DashboardResponse) -> str:
    """把 Dashboard 数据转成给 LLM 的结构化文本（只喂关键指标）。"""
    o = dashboard.overview
    lines = [
        f"统计窗口：{len(dashboard.trend)} 天；学生总数 {o.total_students}；"
        f"今日活跃 {o.active_today}；累计对话 {o.total_sessions}；"
        f"待关注学生 {o.pending_alert_count}。"
    ]
    if dashboard.trend:
        peak = max(dashboard.trend, key=lambda t: t.session_count)
        active_days = sum(1 for t in dashboard.trend if t.session_count > 0)
        avg = o.total_sessions / len(dashboard.trend)
        lines.append(
            f"趋势：互动峰值 {peak.date}（{peak.session_count} 次）；"
            f"有互动天数 {active_days}；日均 {avg:.1f} 次。"
        )
    ms = dashboard.message_stats
    lines.append(
        f"消息级互动：总 {ms.total_messages} 条（学生发起 {ms.student_messages}，"
        f"AI 回复 {ms.assistant_messages}），平均每会话 {ms.avg_turns} 轮，"
        f"知识命中率 {ms.knowledge_hit_rate * 100:.1f}%。"
    )
    lines.append(f"涉及班级数：{len(dashboard.class_comparison)}。")
    return "\n".join(lines)


async def generate_summary(dashboard: DashboardResponse) -> str:
    """生成 LLM 研究摘要；不可用时抛 SummaryUnavailable。"""
    if not _key_available():
        raise SummaryUnavailable("DASHSCOPE_API_KEY 未配置或为占位符")

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(dashboard)},
        ],
        "temperature": 0.4,
        "stream": False,
    }
    url = f"{settings.dashscope_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        if not text:
            raise SummaryUnavailable("LLM 返回空摘要")
        return text
    except SummaryUnavailable:
        raise
    except Exception as exc:  # 网络/超时/非 2xx/解析异常统一降级，不影响学情总览
        logger.warning("LLM summary request failed: %s", exc)
        raise SummaryUnavailable("LLM 摘要服务异常") from exc
