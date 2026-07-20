# 认证授权体系设计

## 背景

教学 Agent 后端需要区分学生端和教师端。当前 `core/deps.py` 用 `X-User-Id` header 模拟认证，无 User 表，无密码，无角色隔离。需要落地真实认证。

## 需求

1. 两种角色：`student` / `teacher`
2. 不绑定学生与教师的关系
3. 学生隔离会话（只看自己的）
4. 教师之间不隔离会话（看所有），但能 CRUD 自己创建的会话（测试用）
5. 数据库不过度设计

## 决策

- **认证方式**：Token 表（有状态，可主动吊销）
- **账号创建**：全部后台/种子 SQL 创建，无注册 API
- **数据模型**：方案 B - `session.user_id` 改 UUID FK，现有 demo 数据删除

## 数据模型

### 新增表

#### User

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| username | str, unique, indexed | 登录用 |
| password_hash | str | bcrypt |
| role | str, indexed | "student" / "teacher" |
| name | str | 显示名 |
| created_at | datetime | |

#### AuthToken

| 字段 | 类型 | 说明 |
|------|------|------|
| token | str PK | uuid4 hex (32 chars) |
| user_id | UUID FK -> user.id, indexed | ondelete CASCADE |
| created_at | datetime | |

无过期时间，登出 = 删除 token 行。

### 修改 Session 表

- `user_id: str` -> `user_id: UUID`
- 增加 `ForeignKey("user.id", ondelete="CASCADE")`
- 现有 demo 数据删除，重建表

### 关系

- User 1:N Session（通过 user_id）
- User 1:N AuthToken（cascade delete）

## 模块结构

### db/models.py

新增 `User`、`AuthToken` 模型。修改 `Session.user_id` 类型为 UUID + FK。

### db/repos.py

新增数据访问函数：
- `get_user_by_username(session, username) -> User | None`
- `get_user_by_id(session, user_id) -> User | None`
- `create_user(session, username, password_hash, role, name) -> User`
- `create_token(session, user_id) -> AuthToken`（生成 uuid4 hex）
- `get_token_with_user(session, token) -> AuthToken | None`（含 user 关联，eager load）
- `delete_token(session, token) -> bool`

### auth/service.py

认证业务逻辑：
- `login(db, username, password) -> str`：查 user -> bcrypt 验证密码 -> 创建 token -> 返回 token
- `logout(db, token)`：删除 token 行，不存在也静默成功
- `verify_token(db, token) -> User`：查 token 表 -> 返回关联 User，不存在抛 `AppError(401, "INVALID_TOKEN", ...)`

### auth/router.py

3 个端点：

```
POST /auth/login     body: {username, password}  -> {token, user: {id, username, role, name}}
POST /auth/logout    (需认证)                     -> 204
GET  /auth/me        (需认证)                     -> {id, username, role, name}
```

### core/deps.py 改造

`get_current_user` 改为：
1. 从 `Authorization: Bearer <token>` header 读 token
2. 调 `auth.service.verify_token()` 查 DB
3. 返回 `CurrentUser(id: UUID, role: str, name: str)`
4. 移除旧的 `X-User-Id` header 逻辑

`CurrentUser` dataclass 改动：
- `id` 类型 `str` -> `UUID`
- 新增 `name: str`

## 授权逻辑

### 权限矩阵

| 操作 | 学生 | 教师 |
|------|------|------|
| 创建会话 POST /sessions | ✅ 自己的 | ✅ 自己的 |
| 列表会话 GET /sessions | 仅自己的 | 全部 |
| 获取会话 GET /sessions/{id} | 仅自己的 | 全部 |
| 获取消息 GET /sessions/{id}/messages | 仅自己的 | 全部 |
| 获取题目 GET /sessions/{id}/questions | 仅自己的 | 全部 |
| 结束会话 DELETE /sessions/{id} | 仅自己的 | 仅自己的 |
| 聊天 POST /sessions/{id}/messages | 仅自己的 | 仅自己的 |
| 答题 POST /sessions/{id}/questions/{qid}/answer | 仅自己的 | 仅自己的 |
| 管理 Projects CRUD /projects | ❌ 403（只读 published） | ✅ 全部 |

### 统一规则

- **写操作**（end/stream/resume）：`session.user_id == user.id`，不分角色（谁创建谁能写）
- **读操作**：学生只看自己的；教师看所有
- **Projects**：写操作（create/update/delete）限教师；读操作不限角色（学生可看 published，教师可看全部）

### chat/service.py 改造

现有 `get_owned_session` 拆分为两个函数：

```python
async def get_readable_session(db, session_id, user) -> Session:
    """读权限：学生检查归属，教师跳过。"""
    sess = await repos.get_session(db, session_id)
    if not sess:
        raise AppError(404, "SESSION_NOT_FOUND", ...)
    if user.role == "student" and sess.user_id != user.id:
        raise AppError(403, "FORBIDDEN", ...)
    return sess

async def get_writable_session(db, session_id, user) -> Session:
    """写权限：不分角色，强制归属检查。"""
    sess = await repos.get_session(db, session_id)
    if not sess:
        raise AppError(404, "SESSION_NOT_FOUND", ...)
    if sess.user_id != user.id:
        raise AppError(403, "FORBIDDEN", ...)
    return sess
```

`list_sessions`：
- 学生：`repos.list_sessions(user_id=user.id, ...)`
- 教师：`repos.list_sessions(user_id=None, ...)`

`repos.list_sessions` 签名改：`user_id: str` -> `user_id: UUID | None`（None 时不按 user 过滤）。

### 路由层改动

读端点（get_session / list_messages / list_questions）用 `get_readable_session`。
写端点（end_session / stream_chat / resume_quiz）用 `get_writable_session`。
create_session 不变（任何角色可创建，user_id 来自 CurrentUser）。

### projects/router.py 改造

当前 projects 路由无认证（无 `get_current_user` 依赖）。补充：
- 所有端点加 `Depends(get_current_user)`（需登录）
- 写端点（create/update/delete）检查 `user.role == "teacher"`，否则 403
- 读端点（list/get）不限角色

## 依赖

- `passlib[bcrypt]`：密码哈希

## 种子数据

后台/种子 SQL 创建账号示例：

```sql
-- 教师
INSERT INTO "user" (id, username, password_hash, role, name, created_at)
VALUES (
  gen_random_uuid(),
  'teacher1',
  '$2b$$...',  -- bcrypt hash
  'teacher',
  '测试教师',
  now()
);

-- 学生
INSERT INTO "user" (id, username, password_hash, role, name, created_at)
VALUES (
  gen_random_uuid(),
  'student1',
  '$2b$$...',
  'student',
  '测试学生',
  now()
);
```

也可提供 `scripts/seed_users.py` 脚本用 Python bcrypt 生成 hash 后插入。

## 现有 demo 数据处理

- 删除 session/message/question 表中 `user_id = 'demo-student'` 的数据
- 重建表（SQLModel 自动建表，需 drop 旧表或 alembic 迁移）
- `projects` 表数据不受影响

## 迁移策略

当前无 alembic 迁移工具，开发阶段直接 drop + recreate：
1. 删除 session/message/question/user/auth_token 表
2. 应用启动时 SQLModel `create_all()` 自动建新表
3. 用种子脚本插入测试账号

生产环境后续接入 alembic。
