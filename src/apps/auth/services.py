from datetime import timedelta
from fastapi import HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.master.user import User
from common.schemas.master.user import (
    LoginSchema,
    CashCounterLoginSchema,
)
from components.utils.password_utils import verify_password
from components.utils.security import create_access_token


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, request: Request, login_data: LoginSchema):
        try:
            query = select(User).where(
                or_(
                    User.user_code == login_data.identifier,
                    User.email == login_data.identifier,
                )
            )
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            if not user or not verify_password(login_data.password, user.password):
                raise HTTPException(
                    status_code=401, detail="Invalid user code or password"
                )
            access_token = create_access_token(
                data={"id": str(user.id), "type": "access"},
                expires_delta=timedelta(days=1),
            )
            request.state.user = user
            return {
                "detail": f"Welcome, {user.username}",
                "access_token": access_token,
                "token_type": "bearer",
            }
        except Exception as e:
            raise e

    async def cash_counter_login(self, request: Request, login_data: CashCounterLoginSchema):
        try:
            from common.models.billing.cash_counter import CashCounter
            
            # 1. Verify credentials (identifier is the Cash Counter Code)
            query = select(CashCounter).where(
                CashCounter.code == login_data.identifier
            )
            result = await self.db.execute(query)
            counter = result.scalar_one_or_none()
            
            if not counter or not verify_password(login_data.password, counter.password):
                raise HTTPException(
                    status_code=401, detail="Invalid counter code or password"
                )
            
            if not counter.is_active:
                 raise HTTPException(status_code=400, detail="Cash Counter is not active")

            # 2. Generate Token with identity_type="cash_counter"
            # Note: We use counter.id as the subject "id"
            access_token = create_access_token(
                data={
                    "id": str(counter.id), 
                    "type": "access",
                    "identity_type": "cash_counter",
                    "counter_id": str(counter.id) # kept for backward compatibility if needed, though redundant with id
                },
                expires_delta=timedelta(days=1),
            )
            
            request.state.cash_counter = counter
            return {
                "detail": f"Welcome, Cash Counter {counter.name}",
                "access_token": access_token,
                "token_type": "bearer",
            }
        except Exception as e:
            raise e

    async def get_current_user(self, request):
        try:
            user = request.state.user
            if not user:
                raise HTTPException(status_code=401, detail="Unauthorized")
            return user
        except Exception as e:
            raise e
