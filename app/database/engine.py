import os

from dotenv import load_dotenv
from langchain_postgres import PGEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

load_dotenv()

DB_URL = os.getenv("DB_URL")

# URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
URL = DB_URL

engine = create_async_engine(
    URL,
    echo=False,
)

pg_engine = PGEngine.from_connection_string(url=URL)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session():
    async with async_session() as session:
        yield session
