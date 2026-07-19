"""认证授权模块（预留）。

当前认证由 core.deps.get_current_user 以 X-User-Id 请求头实现。
未来在此落地：JWT 校验器、User 模型、role（teacher/student）判定；
core.deps.get_current_user 将改为委托本模块，路由签名不变。
"""
