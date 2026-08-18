import type { Message } from "@langchain/langgraph-sdk";

export type QuizType = "single" | "multi" | "short";

/** 兼容数组 / JSON 字符串 / null，语义对齐后端 schemas.py 的 coerce_options */
export function coerceQuizOptions(value: unknown): string[] | null {
  if (value == null) return null;
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) return parsed.map(String);
    } catch {
      // fall through
    }
    return [value];
  }
  return null;
}

export type QuizToolResult = {
  studentAnswer: string | null;
  skipped: boolean;
};

export function parseQuizToolResult(content: unknown): QuizToolResult | null {
  if (typeof content !== "string") return null;
  try {
    const parsed = JSON.parse(content);
    if (!parsed || typeof parsed !== "object") return null;
    if (parsed.action === "skipped") return { studentAnswer: null, skipped: true };
    if (typeof parsed.student_answer === "string")
      return { studentAnswer: parsed.student_answer, skipped: false };
    return null;
  } catch {
    return null;
  }
}

/** 高亮匹配：优先按 ", " 分割精确匹配（多选提交格式），兜底双向包含 */
export function isOptionSelected(option: string, studentAnswer: string): boolean {
  const parts = studentAnswer.split(", ").map((s) => s.trim());
  if (parts.includes(option)) return true;
  return studentAnswer.includes(option) || option.includes(studentAnswer);
}

/** 按 tool_call_id 在 AI 消息里找 present_question 的 tool-call */
export function findPresentQuestionToolCall(
  messages: Message[],
  toolCallId: string | undefined,
): { name: string; args: Record<string, unknown>; id?: string } | undefined {
  if (!toolCallId) return undefined;
  for (const m of messages) {
    const calls = (m as { tool_calls?: unknown[] }).tool_calls;
    if (!Array.isArray(calls)) continue;
    for (const tc of calls) {
      const c = tc as { name?: string; id?: string; args?: unknown };
      if (c.name === "present_question" && c.id === toolCallId) {
        return {
          name: c.name,
          id: c.id,
          args: (c.args ?? {}) as Record<string, unknown>,
        };
      }
    }
  }
  return undefined;
}
