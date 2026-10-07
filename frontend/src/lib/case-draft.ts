export type CaseDraftToolResult = {
  ok: boolean;
  projectId: string | null;
  projectName: string | null;
  stageCount: number;
  created: boolean;
  error: string | null;
};

export function parseCaseDraftResult(
  content: unknown,
): CaseDraftToolResult | null {
  if (typeof content !== "string") return null;
  try {
    const parsed = JSON.parse(content);
    if (!parsed || typeof parsed !== "object") return null;
    if (parsed.ok === true && typeof parsed.project_id === "string") {
      return {
        ok: true,
        projectId: parsed.project_id,
        projectName: String(parsed.project_name ?? ""),
        stageCount: Number(parsed.stage_count ?? 0),
        created: !!parsed.created,
        error: null,
      };
    }
    if (parsed.ok === false) {
      return {
        ok: false,
        projectId: null,
        projectName: null,
        stageCount: 0,
        created: false,
        error: String(parsed.error ?? "保存失败，请重试"),
      };
    }
    return null;
  } catch {
    return null;
  }
}
