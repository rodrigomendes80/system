from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import create_database
from app.routers import clientes, projetos, tarefas
from app.services import NaoEncontrado, RegraDeNegocioViolada


def create_app(db=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db = db or create_database(get_settings())
        yield
        app.state.db.close()

    app = FastAPI(
        title="Gestão de Projetos e Tarefas",
        description="Clientes → Projetos → Tarefas, com persistência em Databricks.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(NaoEncontrado)
    async def _nao_encontrado(_: Request, exc: NaoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RegraDeNegocioViolada)
    async def _regra(_: Request, exc: RegraDeNegocioViolada):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    app.include_router(clientes.router)
    app.include_router(projetos.router)
    app.include_router(tarefas.router)
    return app


app = create_app()
