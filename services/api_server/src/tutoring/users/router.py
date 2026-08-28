from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.core.deps import CurrentUser, get_current_user, get_db
from tutoring.core.errors import AppError
from tutoring.core.schemas import Page
from tutoring.db import repos
from tutoring.sessions import service as session_service
from tutoring.sessions.schemas import SessionOut
from tutoring.users import service as user_service
from tutoring.users.schemas import ImportResult, UserOut

router = APIRouter(prefix="/users", tags=["users"])


def _require_teacher(user: CurrentUser) -> None:
    if user.role != "teacher":
        raise AppError(403, "TEACHER_ONLY", "仅教师可执行此操作")


""" @router.get("/students", response_model=Page[UserOut])
async def list_students(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> Page[UserOut]:
    _require_teacher(user)
    offset = (page - 1) * page_size
    students = await user_service.list_students(db_session, limit=page_size, offset=offset)
    total = await repos.count_users_by_role(db_session, "student")
    return Page(
        items=[UserOut.model_validate(s) for s in students],
        total=total,
        page=page,
        page_size=page_size,
    ) """


@router.get("/teachers", response_model=list[UserOut])
async def list_teachers(
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    _require_teacher(user)
    teachers = await user_service.list_teachers(db_session)
    return [UserOut.model_validate(t) for t in teachers]

""" 
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> None:
    _require_teacher(user)
    await user_service.delete_student(db_session, user_id) """


""" @router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> dict:
    _require_teacher(user)
    await user_service.reset_password(db_session, user_id)
    return {"message": "密码已重置为 123456"} """

""" 
@router.get("/{user_id}/sessions", response_model=Page[SessionOut])
async def list_user_sessions(
    user_id: UUID,
    mode: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> Page[SessionOut]:
    _require_teacher(user)
    offset = (page - 1) * page_size
    sessions = await repos.list_sessions(
        db_session,
        user_id=user_id,
        mode=mode,
        limit=page_size,
        offset=offset,
    )
    total = await repos.count_sessions(db_session, user_id=user_id, mode=mode)
    return Page(
        items=[SessionOut.model_validate(session_service.session_to_out_dict(s)) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
    ) """


""" @router.post("/students/import", response_model=ImportResult)
async def import_students(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> ImportResult:
    _require_teacher(user)
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise AppError(422, "INVALID_FILE", "请上传 .xlsx 或 .xls 文件")
    content = await file.read()
    return await user_service.import_students(db_session, content) """


@router.get("/students/template")
async def download_template(
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    _require_teacher(user)
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["学号", "姓名", "密码"])
    ws.append(["2023001", "张三", "zs123"])
    ws.append(["2023002", "李四", "ls123"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=students_template.xlsx"},
    )


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db),
) -> dict:
    content = await file.read()
    avatar_url = await user_service.upload_avatar(
        db_session, user.id, content, file.content_type or ""
    )
    return {"avatar_url": avatar_url}
