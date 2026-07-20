"""用户管理路由：列表/删除/重置密码/Excel 导入。全部限教师。"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.db import repos
from tutoring.users import service as user_service
from tutoring.users.schemas import ImportResult, UserOut

router = APIRouter(prefix="/users", tags=["users"])


def _require_teacher(user: CurrentUser) -> None:
    if user.role != "teacher":
        raise AppError(403, "TEACHER_ONLY", "仅教师可执行此操作")


@router.get("/students", response_model=list[UserOut])
async def list_students(
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    _require_teacher(user)
    students = await user_service.list_students(db_session)
    return [UserOut.model_validate(s) for s in students]


@router.get("/teachers", response_model=list[UserOut])
async def list_teachers(
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    _require_teacher(user)
    teachers = await user_service.list_teachers(db_session)
    return [UserOut.model_validate(t) for t in teachers]


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    _require_teacher(user)
    await user_service.delete_student(db_session, user_id)


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> dict:
    _require_teacher(user)
    await user_service.reset_password(db_session, user_id)
    return {"message": "密码已重置为 123456"}


@router.post("/students/import", response_model=ImportResult)
async def import_students(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ImportResult:
    _require_teacher(user)
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise AppError(422, "INVALID_FILE", "请上传 .xlsx 或 .xls 文件")
    content = await file.read()
    return await user_service.import_students(db_session, content)
