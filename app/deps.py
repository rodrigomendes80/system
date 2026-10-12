from fastapi import Request

from app.db.base import Database


def get_db(request: Request) -> Database:
    return request.app.state.db
