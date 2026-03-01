import aiomysql
from app.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

pool: aiomysql.Pool | None = None


async def init_pool():
    global pool
    pool = await aiomysql.create_pool(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASSWORD, db=DB_NAME,
        autocommit=True, minsize=2, maxsize=10,
    )
    return pool


async def close_pool():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        pool = None


def get_pool() -> aiomysql.Pool:
    if not pool:
        raise RuntimeError("DB pool not initialized")
    return pool


async def fetch_one(query: str, args: tuple = ()) -> dict | None:
    async with get_pool().acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, args)
            return await cur.fetchone()


async def fetch_all(query: str, args: tuple = ()) -> list[dict]:
    async with get_pool().acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, args)
            return await cur.fetchall()


async def execute(query: str, args: tuple = ()) -> int:
    async with get_pool().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, args)
            await conn.commit()
            return cur.lastrowid