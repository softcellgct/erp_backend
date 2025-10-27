from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr


class UserCreateSchema(BaseModel):
    email : EmailStr
    user_code: str
    username: str
    full_name: str
    password: str
    role_id: UUID

class UserUpdateSchema(BaseModel):
    email : Optional[EmailStr] | None = None
    user_code: Optional[str] | None = None
    username: Optional[str] | None = None
    full_name: Optional[str] | None = None
    password: Optional[str] | None = None
    role_id: Optional[UUID] | None = None

class UserResponseSchema(BaseModel):
    id: UUID
    email : EmailStr
    user_code: str
    username: str
    full_name: str
    role_id: UUID

    class Config:
        from_attributes = True
    
class LoginSchema(BaseModel):
    identifier: str
    password: str

class PermissionAssignSchema(BaseModel):
    role_id: UUID
    screen_id: UUID
    can_view: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False