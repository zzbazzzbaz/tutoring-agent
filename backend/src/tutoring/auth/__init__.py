"""认证授权模块：token 表 + bcrypt 密码 + 角色（teacher/student）。

router: POST /auth/login, POST /auth/logout, GET /auth/me
service: login / logout / verify_token / hash_password / verify_password
core.deps.get_current_user 委托 auth.service.verify_token 校验 Bearer token。
"""
