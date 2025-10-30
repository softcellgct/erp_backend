from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    minio_endpoint: str
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool
    minio_bucket: str

    class Config:
        env_file = "/home/backend/backend/src/.env"


settings = Settings()
