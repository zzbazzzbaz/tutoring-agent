"""所有 prompt 模板。

Prompt 是教学效果的核心，修改 prompt 后在 notebook 中重新运行即可看到效果变化。
"""

# === 知识图谱分析 prompt（入库时逐 chunk 调用）===

CHUNK_ANALYSIS_PROMPT = """你是一位知识图谱构建专家。

## 任务
分析以下知识片段，提取知识点和知识点之间的关系。

## 知识片段
内容：{chunk_content}
标题路径：{heading_path}

## 已有知识点列表（优先复用，避免重名）
{existing_kps}

## 需要输出
1. knowledge_points: 这个片段涉及的知识点
   - 优先复用已有知识点（is_new=false）
   - 确需新增才创建（is_new=true）
   - 每个知识点给简短描述
2. edges: 这些知识点之间的关系
   - part_of: A是B的子主题（source 是子，target 是父）
   - prerequisite: 学A之前必须先学B（source 需要先学 target）
   - related: A和B概念相关
   - contrast: A和B容易混淆
"""
