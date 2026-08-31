"""功能模块：项目学习进度

- 内部端点：Agent Server 更新学生学习进度（项目学习主线）
- 查询端点：教师查看任意学生进度，学生查看自己的进度
"""
from tutoring.progress import router

__all__ = ["router"]
