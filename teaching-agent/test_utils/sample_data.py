"""示例知识库内容，从 docs/test-input-docs/ 加载。

测试用数据，不属于生产代码。notebook 入库时用这些文档验证 RAG 流程。
"""
from pathlib import Path

# 知识库文档目录：test_utils/ -> teaching-agent/ -> 教学Agent/ -> docs/test-input-docs
_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "test-input-docs"

# 课程级文档文件列表
_COURSE_DOC_FILES = [
    {"filename": "物理层.md", "scope": "course"},
    {"filename": "数据链路层.md", "scope": "course"},
    {"filename": "数据链路层-PPP与HDLC.md", "scope": "course"},
    {"filename": "物理层与数据链路层综合.md", "scope": "course"},
]


def load_course_documents() -> list[dict]:
    """加载课程级知识库文档。

    Returns:
        文档列表，每个含 filename, scope, content
    """
    docs = []
    for doc_info in _COURSE_DOC_FILES:
        filepath = _DOCS_DIR / doc_info["filename"]
        content = filepath.read_text(encoding="utf-8")
        docs.append(
            {
                "filename": doc_info["filename"],
                "scope": doc_info["scope"],
                "content": content,
            }
        )
    return docs


# 直接可用的文档列表
COURSE_DOCUMENTS = load_course_documents()

# 项目级文档（原型阶段一个示例）
PROJECT_DOCUMENTS = [
    {
        "filename": "wireshark_analysis.md",
        "scope": "project",
        "project_name": "Wireshark 抓包分析 TCP 连接",
        "background_md": """## 项目背景

使用 Wireshark 抓取本机访问网站时的 TCP 流量，分析三次握手和四次挥手过程。

## 任务要求
1. 启动 Wireshark，过滤 TCP 流量
2. 访问一个 HTTP 网站
3. 找到三次握手的三个包，记录序号和标志位
4. 找到四次挥手的四个包
5. 分析 TIME_WAIT 状态的等待时间
""",
        "content": """# Wireshark 抓包分析指南

## 抓包步骤

1. 打开 Wireshark，选择活跃的网络接口
2. 设置过滤器：`tcp and ip.addr == 目标IP`
3. 在浏览器中访问目标网站
4. 停止抓包，分析 TCP 流

## 识别三次握手

在 Wireshark 中寻找连续三个 TCP 包：
- SYN（标志位 SYN=1）
- SYN, ACK（标志位 SYN=1, ACK=1）
- ACK（标志位 ACK=1）

查看每个包的 Sequence Number 和 Acknowledgment Number，验证 x -> y -> x+1 -> y+1 的关系。

## 识别四次挥手

寻找 FIN 标志位的包：
- FIN, ACK
- ACK
- FIN, ACK
- ACK

注意 TIME_WAIT 状态持续的时间（最后一个 ACK 发出后到连接完全关闭）。
""",
    },
]
