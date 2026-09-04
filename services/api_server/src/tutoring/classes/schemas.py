# 响应模型
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# 创建班级表信息
class ClassCreate(BaseModel):
    grade: str = Field(min_length=1, max_length=50)
    classname: str = Field(min_length=1, max_length=20)

# 更新班级表信息
class ClassUpdate(BaseModel):
    grade: str | None = Field(default=None, min_length=1, max_length=50)
    classname: str | None = Field(default=None, min_length=1, max_length=20)
    status: Literal["active", "archived"] | None = None

# 查询班级表信息
class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grade: str
    classname: str
    teacher_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    student_count: int = 0
    teacher_name: str | None = None

# 导入班级学生结果
class ImportResult(BaseModel):
    total: int
    created: int
    # 导入文件中已存在且未删除的学生账号，已并入当前班级的数量
    joined_existing: int = 0
    skipped: int
    errors: list[str]


# 查询班级学生信息
class ClassStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    username: str
    name: str
    joined_at: datetime

# 查询班级会话信息
class ClassSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_name: str | None = None
    username: str | None = None
    title: str | None = None
    mode: str
    project_id: UUID | None = None
    project_name: str | None = None
    last_active_at: datetime
    created_at: datetime

# 查询班级统计信息
class ClassStats(BaseModel):
    total_students: int
    total_sessions: int
    active_today: int

# 批量添加班级学生
class AddStudentsRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1)

# 批量移除班级学生
class RemoveStudentsRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1)

# 批量软删除学生账号
class SoftDeleteRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)