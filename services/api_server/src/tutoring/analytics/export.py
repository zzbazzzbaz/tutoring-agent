# 统计分析--报告导出（Word）
# analytics/export.py
"""使用统计报告导出为 Word 文档（.docx）。

样式对齐参考稿《使用统计报告_2026-08-17_2026-08-30.docx》：
- 字体：全文微软雅黑（Microsoft YaHei）
- 主色：#1F5EDC（标题/章节/表头文字），表头底纹 #EEF4FF，
  表格数据 #334155，摘要正文 #0F172A，报告头 #64748B
- 表格边框：#D9E2EF 浅蓝细线（1/8pt）
- 页面：横向 A4（29.7×21.0cm），边距 1.27cm

数据来源与前端报告页一致：
- DashboardResponse（核心指标 / 互动明细 / 趋势 / 班级对比 / 排行 / 重点学生）
- ProjectProgressResponse（阶段分布 / 产出物完成）
- ClassEvaluationResponse（班级评价六维）
「数据摘要」板块使用规则摘要（与前端 buildSummary 口径一致，不依赖 LLM key）。
"""
from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from tutoring.analytics.schemas import (
    ClassEvaluationResponse,
    DashboardResponse,
    ProjectProgressResponse,
)

# ===== 样式常量（对齐参考稿） =====
_FONT = "Microsoft YaHei"  # 微软雅黑（含 eastAsia）
_COLOR_PRIMARY = RGBColor(0x1F, 0x5E, 0xDC)  # 标题/章节/表头文字 蓝
_COLOR_BODY = RGBColor(0x0F, 0x17, 0x2A)  # 摘要正文 深蓝黑
_COLOR_TABLE = RGBColor(0x33, 0x41, 0x55)  # 表格数据 深灰蓝
_COLOR_MUTED = RGBColor(0x64, 0x74, 0x8B)  # 报告头 灰
_HEADER_SHADING = "EEF4FF"  # 表头底纹 浅蓝
_BORDER_COLOR = "D9E2EF"  # 表格边框 浅蓝
_BORDER_SZ = "1"  # 1/8pt
# 表格可用宽度 = 横向页面 29.7 - 左右边距 1.27*2（表格顶到两侧）
USABLE_WIDTH_CM = 29.7 - 1.27 * 2


def _set_cell_shading(cell, color_hex: str) -> None:
    """设置单元格底纹。"""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), color_hex)


def _set_table_borders(table) -> None:
    """设置表格边框为浅蓝细线（对齐参考稿 D9E2EF / sz=1）。"""
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:color"), _BORDER_COLOR)
        el.set(qn("w:sz"), _BORDER_SZ)
        borders.append(el)
    tbl_pr.append(borders)


def _set_run_font(run, *, size: float, bold: bool = False, color: RGBColor | None = None) -> None:
    """设置 run 字体（微软雅黑 + eastAsia + 字号/颜色）。"""
    run.font.name = _FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), _FONT)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _add_heading(doc: Document, text: str) -> None:
    """章节标题：14pt 加粗，主色蓝。"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    _set_run_font(run, size=14, bold=True, color=_COLOR_PRIMARY)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)


def _add_body(doc: Document, text: str, *, bold: bool = False, size: float = 10.5, color: RGBColor | None = None) -> None:
    """正文段落（默认 10.5pt 深蓝黑）。"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    _set_run_font(run, size=size, bold=bold, color=color or _COLOR_BODY)
    p.paragraph_format.space_after = Pt(2)


def _add_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    *,
    col_widths_cm: list[float] | None = None,
) -> None:
    """添加表格：表头浅蓝底纹 + 蓝色加粗文字，数据深灰蓝，浅蓝细线边框。

    表格总宽占满可用宽度（顶到页面两侧）：指定列宽时按比例放大，
    未指定时平均分配。
    """
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders(table)
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        run = hdr[i].paragraphs[0].add_run(h)
        _set_run_font(run, size=10, bold=True, color=_COLOR_PRIMARY)
        _set_cell_shading(hdr[i], _HEADER_SHADING)
    for r in rows:
        cells = table.add_row().cells
        for i, v in enumerate(r):
            run = cells[i].paragraphs[0].add_run(str(v))
            _set_run_font(run, size=9.5, color=_COLOR_TABLE)
    # 列宽：按比例放大至可用宽度（顶到两侧）
    n = len(headers)
    if col_widths_cm:
        total = sum(col_widths_cm)
        scale = USABLE_WIDTH_CM / total if total > 0 else 1.0
        widths = [w * scale for w in col_widths_cm]
    else:
        widths = [USABLE_WIDTH_CM / n] * n
    for i, w in enumerate(widths):
        for row in table.rows:
            row.cells[i].width = Cm(w)
    table.autofit = False
    # 表格总宽 = 可用宽度（顶到两侧）。python-docx 1.2.0 不支持 Table.width，
    # 直接写入 w:tblW（dxa 单位，1cm = 567 twips；按 schema 顺序插到 tblPr 最前）
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.insert(0, tbl_w)
    tbl_w.set(qn("w:type"), "dxa")
    tbl_w.set(qn("w:w"), str(int(USABLE_WIDTH_CM * 567)))


def _build_rule_summary_lines(dashboard: DashboardResponse, days: int, scope_label: str) -> list[str]:
    """规则版数据摘要（与前端 buildSummary 口径一致），按行返回（每行一个要点）。"""
    trend = dashboard.trend or []
    window_sessions = sum(t.session_count for t in trend)
    daily_avg = round(window_sessions / len(trend), 1) if trend else 0.0
    active_days = sum(1 for t in trend if t.session_count > 0)
    # 峰值：与前端 report/page.tsx reduce 口径一致（>= 比较，并列取较新日期）
    peak = None
    for t in trend:
        if peak is None or t.session_count >= peak.session_count:
            peak = t
    ov = dashboard.overview
    start = trend[0].date if trend else "-"
    end = trend[-1].date if trend else "-"

    lines: list[str] = []
    lines.append(f"统计范围：{start} 至 {end}（{days} 天），覆盖 {scope_label}。")
    lines.append(
        f"窗口活跃：统计窗口内对话 {window_sessions} 次，日均 {daily_avg} 次；"
        f"历史累计对话 {ov.total_sessions} 次。"
    )
    if peak and peak.session_count > 0:
        lines.append(
            f"趋势观察：{active_days} 天有学生互动，互动峰值出现在 {peak.date}（{peak.session_count} 次）。"
        )
    else:
        lines.append("趋势观察：统计窗口内暂无对话记录。")
    lines.append(
        f"重点跟进：当前有 {ov.pending_alert_count} 名学生需要重点关注，建议及时跟进。"
        if ov.pending_alert_count > 0
        else "重点跟进：当前无待关注学生。"
    )
    ms = dashboard.message_stats
    if ms and ms.total_messages > 0:
        lines.append(
            f"消息互动：总互动 {ms.total_messages} 条（学生发起 {ms.student_messages}，"
            f"AI 回复 {ms.assistant_messages}），平均每会话 {ms.avg_turns} 轮，"
            f"知识命中率 {round(ms.knowledge_hit_rate * 100)}%。"
        )
    return lines


def build_report_docx(
    *,
    dashboard: DashboardResponse,
    progress: ProjectProgressResponse,
    evaluation: ClassEvaluationResponse,
    scope_label: str,
    days: int,
    generated_at: datetime,
) -> io.BytesIO:
    """构建使用统计报告 Word 文档，返回 BytesIO（docx 文件流）。"""
    doc = Document()

    # 页面：横向 A4，边距 1.27cm（对齐参考稿）
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Cm(29.7)
    section.page_height = Cm(21.0)
    section.top_margin = Cm(1.27)
    section.bottom_margin = Cm(1.27)
    section.left_margin = Cm(1.27)
    section.right_margin = Cm(1.27)

    # Normal 样式默认字体
    normal = doc.styles["Normal"]
    normal.font.name = _FONT
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), _FONT)
    normal.font.size = Pt(10.5)

    # 大标题：20pt 加粗 主色蓝 居中
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run("使用统计报告")
    _set_run_font(title_run, size=20, bold=True, color=_COLOR_PRIMARY)
    title_p.paragraph_format.space_after = Pt(4)

    # 报告头：11pt 灰色 居中（一行）
    trend = dashboard.trend or []
    start_date = trend[0].date if trend else "-"
    end_date = trend[-1].date if trend else "-"
    gen_str = generated_at.strftime("%Y-%m-%d %H:%M")
    head_p = doc.add_paragraph()
    head_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    head_run = head_p.add_run(
        f"统计范围：{start_date} 至 {end_date}    生成时间：{gen_str}    班级：{scope_label}"
    )
    _set_run_font(head_run, size=11, color=_COLOR_MUTED)
    head_p.paragraph_format.space_after = Pt(6)

    # 一、核心指标
    _add_heading(doc, "核心指标")
    ov = dashboard.overview
    _add_table(
        doc,
        ["指标", "数值", "说明"],
        [
            ["学生总数", str(ov.total_students), "班级总学生数"],
            ["今日活跃", f"{ov.active_today} / {ov.total_students}", "当日有对话记录的学生"],
            ["累计对话", f"{ov.total_sessions} 次", "历史累计对话总数"],
            ["待关注", str(ov.pending_alert_count), "高风险 / 高优先级学生数"],
        ],
        col_widths_cm=[4.5, 6.0, 14.0],
    )

    # 二、互动明细
    _add_heading(doc, "互动明细")
    ms = dashboard.message_stats
    _add_table(
        doc,
        ["指标", "数值", "说明"],
        [
            ["总互动", str(ms.total_messages), "学生发起与 AI 回复合计"],
            ["学生发起", str(ms.student_messages), "学生消息数"],
            ["AI回复(轮次)", str(ms.assistant_messages), "AI 回复消息数"],
            ["平均轮次", f"{ms.avg_turns} 轮", "AI回复 / 窗口内有消息的会话数"],
            ["知识命中率", f"{round(ms.knowledge_hit_rate * 100)}%", "命中知识的学生提问 / 学生提问总数"],
        ],
        col_widths_cm=[4.5, 6.0, 14.0],
    )

    # 三、阶段分布与产出物完成
    _add_heading(doc, "阶段分布与产出物完成")
    if progress.projects:
        headers = ["阶段", "产出物", "已完成", "进行中", "已开始", "产出物提交", "产出物达标"]
        for proj in progress.projects:
            _add_body(
                doc,
                f"{proj.project_name}（参与学生 {proj.student_count}，阶段数 {proj.stage_count}）",
                bold=True,
                color=_COLOR_BODY,
            )
            rows = [
                [
                    st.title,
                    st.deliverable_title or "—",
                    str(st.completed_count),
                    str(st.in_progress_count),
                    str(st.started_count),
                    str(st.deliverable_submitted_count),
                    str(st.deliverable_done_count),
                ]
                for st in proj.stages
            ]
            _add_table(
                doc,
                headers,
                rows,
                col_widths_cm=[4.6, 6.4, 2.0, 2.0, 2.0, 2.6, 2.6],
            )
    else:
        _add_body(doc, "暂无项目进度数据。")

    # 四、数据摘要（多行要点，每行加粗深色）
    _add_heading(doc, "数据摘要")
    for line in _build_rule_summary_lines(dashboard, days, scope_label):
        _add_body(doc, line, bold=True, color=_COLOR_BODY)

    # 五、趋势概览（三日滑动均值与前端口径一致：当天 + 前 2 天）
    _add_heading(doc, "趋势概览")
    # 概览统计（与前端 MiniStat 口径一致：互动峰值 / 有互动天数 / 日均对话）
    peak = None
    for t in trend:
        if peak is None or t.session_count >= peak.session_count:
            peak = t
    active_days = sum(1 for t in trend if t.session_count > 0)
    window_sessions = sum(t.session_count for t in trend)
    daily_avg = round(window_sessions / len(trend), 1) if trend else 0.0
    peak_text = f"{peak.date} · {peak.session_count} 次" if peak and peak.session_count > 0 else "暂无"
    _add_table(
        doc,
        ["互动峰值", "有互动天数", "日均对话"],
        [[peak_text, f"{active_days} 天", f"{daily_avg} 次"]],
        col_widths_cm=[9.0, 8.0, 8.0],
    )
    trend_rows = []
    for i, t in enumerate(trend):
        window = trend[max(0, i - 2): i + 1]
        avg3 = round(sum(x.session_count for x in window) / len(window), 1)
        trend_rows.append([t.date, str(t.session_count), str(t.active_student_count), str(avg3)])
    _add_table(
        doc,
        ["日期", "对话数", "活跃学生", "三日滑动均值"],
        trend_rows,
        col_widths_cm=[8.0, 5.0, 5.0, 7.0],
    )

    # 六、班级活跃率对比
    _add_heading(doc, "班级活跃率对比")
    comp_rows = [
        [
            c.class_name,
            str(c.total_students),
            str(c.active_today),
            f"{round(c.active_rate * 100)}%",
        ]
        for c in dashboard.class_comparison
    ]
    _add_table(
        doc,
        ["班级", "学生数", "今日活跃", "活跃率"],
        comp_rows,
        col_widths_cm=[8.0, 5.0, 5.0, 7.0],
    )

    # 七、学生活跃度排行 TOP10
    _add_heading(doc, "学生活跃度排行 TOP10")
    rank_rows = []
    for i, s in enumerate(dashboard.student_ranking[:10], start=1):
        last = s.last_active_at.strftime("%Y-%m-%d") if s.last_active_at else "-"
        rank_rows.append([str(i), s.username, s.name, str(s.total_sessions), str(s.active_days), last])
    _add_table(
        doc,
        ["排名", "学号", "姓名", "累计对话", "活跃天数", "最后活跃"],
        rank_rows,
        col_widths_cm=[2.4, 4.6, 4.6, 3.6, 3.6, 7.0],
    )

    # 八、重点学生（表格呈现）
    _add_heading(doc, "重点学生")
    if dashboard.key_students:
        key_rows = []
        for ks in dashboard.key_students:
            level_name = "高风险" if ks.level == "high_risk" else "高优先级"
            key_rows.append(
                [ks.name, ks.class_name, level_name, ks.reason, str(ks.session_count), str(ks.assistant_messages)]
            )
        _add_table(
            doc,
            ["姓名", "班级", "级别", "原因", "会话", "AI回复"],
            key_rows,
            col_widths_cm=[3.0, 4.0, 2.4, 12.0, 2.0, 2.0],
        )
    else:
        _add_body(doc, "暂无重点学生。")

    # 九、班级评价（维度 × 班级）
    _add_heading(doc, "班级评价")
    if evaluation.classes:
        headers = ["维度"] + [c.class_name for c in evaluation.classes]
        rows = []
        for dim in evaluation.classes[0].dimensions:
            row = [dim.name]
            for c in evaluation.classes:
                matched = next(
                    (x for x in c.dimensions if x.dimension_id == dim.dimension_id),
                    None,
                )
                row.append(f"{matched.score}（{matched.level}）" if matched else "-")
            rows.append(row)
        _add_table(doc, headers, rows)
    else:
        _add_body(doc, "暂无班级评价数据。")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
