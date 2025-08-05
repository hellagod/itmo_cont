from typing import List

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_NAME: str
    PROGRAM_SLUGS: List[str] = ['ai_product', 'ai']
    OPEN_AI_KEY: str
    TELEGRAM_BOT_TOKEN: str

    @property
    def database_url(self) -> str:
        return str(PostgresDsn.build(
            scheme='postgresql',
            password=self.DB_PASSWORD,
            username=self.DB_USER,
            host=self.DB_HOST,
            port=self.DB_PORT,
            path=self.DB_NAME,
        ))

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = True


settings = Settings()
