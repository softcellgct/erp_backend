
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from apps.auth.services import UserService
from common.schemas.master.user import (
    LoginSchema,
    CashCounterLoginSchema,
)
from components.db.db import get_db_session
from components.middleware import public_route

auth_router = APIRouter()

@auth_router.post("/login", tags=["Auth"])
@public_route
async def login(login_data: LoginSchema, request: Request, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).login(request, login_data)

@auth_router.post("/cash-counter/login", tags=["Auth"])
@public_route
async def cash_counter_login(login_data: CashCounterLoginSchema, request: Request, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).cash_counter_login(request, login_data)

@auth_router.get("/me", tags=["Auth"])
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).get_current_user(request)