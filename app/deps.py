from fastapi import Request

from app.db.base import Database


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_usuario(request: Request) -> str | None:
    """Usuário logado. No Databricks Apps a plataforma envia o e-mail nestes cabeçalhos;
    rodando localmente não há login, e o autor fica em branco."""
    return request.headers.get("x-forwarded-email") or request.headers.get(
        "x-forwarded-preferred-username"
    )
