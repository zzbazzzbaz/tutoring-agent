import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tutoring.auth import router as auth_router
from tutoring.core import health as health_router
from tutoring.core.config import settings
from tutoring.core.database import create_engine, create_session_factory, init_db
from tutoring.core.errors import register_exception_handlers
from tutoring.projects import router as projects_router
from tutoring.sessions import router as sessions_router
from tutoring.users import router as users_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(settings.database_url)
    await init_db(engine)
    app.state.engine = engine
    app.state.db_session_factory = create_session_factory(engine)
    logger.info("DB initialized: %s", settings.database_url)
    yield
    await engine.dispose()
    logger.info("Cleanup complete")


app = FastAPI(title="API Server", version="0.2.0", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(health_router.router)
app.include_router(projects_router.router)
app.include_router(sessions_router.router)
