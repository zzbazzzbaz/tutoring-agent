"""功能模块：消息记录（内部端点）

供 Agent Server 每回合结束后写入消息内容与知识命中标注。
"""
from tutoring.messages import router

__all__ = ["router"]
