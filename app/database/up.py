import asyncio

from sqlmodel import SQLModel

from app.database.engine import engine


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def main():
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
