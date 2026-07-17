"""Markdown 按标题层级切分，每个 chunk 保留完整标题路径。"""
import re
from dataclasses import dataclass


@dataclass
class ChunkResult:
    """切分结果。"""

    content: str  # chunk 正文内容
    heading_path: str  # 完整标题路径，如 "TCP连接管理 > 三次握手"
    chunk_index: int  # 在原文档中的序号


def chunk_markdown(md_text: str, max_chars: int = 1500, overlap: int = 150) -> list[ChunkResult]:
    """按标题层级切分 markdown 文本。

    策略：
    1. 按 # / ## / ### ... 标题分块
    2. 每个 chunk 保留从根标题到当前标题的完整路径（heading_path）
    3. 单 chunk 超过 max_chars 时按段落二次切分，overlap 个字符重叠

    Args:
        md_text: markdown 原文
        max_chars: 单 chunk 最大字符数（约 500 tokens）
        overlap: 二次切分时的重叠字符数

    Returns:
        切分结果列表
    """
    # 按 markdown 标题行分割
    lines = md_text.split("\n")
    sections: list[tuple[int, str, list[str]]] = []  # [(heading_level, heading_text, content_lines), ...]
    current_level = 0
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            # 保存上一个 section
            if current_lines:
                sections.append((current_level, current_heading, current_lines))
            current_level = len(match.group(1))
            current_heading = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # 最后一个 section
    if current_lines:
        sections.append((current_level, current_heading, current_lines))

    # 构建带 heading_path 的 chunks
    results: list[ChunkResult] = []
    heading_stack: list[tuple[int, str]] = []  # [(level, heading), ...]

    for level, heading, content_lines in sections:
        # 更新标题栈：弹出比当前 level >= 的标题
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, heading))

        heading_path = " > ".join(h for _, h in heading_stack)
        content = "\n".join(content_lines).strip()

        if not content:
            continue

        # 二次切分：超长内容按段落分
        if len(content) > max_chars:
            sub_chunks = _split_long_content(content, max_chars, overlap)
            for sub in sub_chunks:
                results.append(
                    ChunkResult(
                        content=sub,
                        heading_path=heading_path,
                        chunk_index=len(results),
                    )
                )
        else:
            results.append(
                ChunkResult(
                    content=content,
                    heading_path=heading_path,
                    chunk_index=len(results),
                )
            )

    return results


def _split_long_content(content: str, max_chars: int, overlap: int) -> list[str]:
    """按段落切分超长内容，带重叠。"""
    paragraphs = content.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            chunks.append(current.strip())
            # 保留 overlap 个字符的上下文
            current = current[-overlap:] + "\n\n" + para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks
