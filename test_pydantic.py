from pydantic import BaseModel

class UserCreateSchema(BaseModel):
    password: str

user_data = UserCreateSchema(password="secret123")
user_data.password = "hashed_secret"
print(user_data.model_dump())
