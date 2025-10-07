from uuid import UUID
from pydantic import BaseModel, EmailStr


class UserCreateSchema(BaseModel):
    email : EmailStr
    user_code: str
    username: str
    full_name: str
    password: str
    role_id: UUID
    
class LoginSchema(BaseModel):
    identifier: str
    password: str