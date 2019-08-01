import asyncpg
from loguru import logger
from flask_login import UserMixin
from config import settings


async def get_db():
    pool = await asyncpg.create_pool(f"{settings['pg']['uri']}/satext", max_size=85)
    return pool


class User(UserMixin):
    def __init__(self, id_, name, email, profile_pic, corps_id):
        # TODO add roles for users (who they can send to)
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic
        self.corps_id = corps_id

    @classmethod
    async def get(cls, user_id):
        pool = await get_db()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(f"SELECT * FROM user WHERE id = {user_id}")
            if not user:
                return None

            user = User(id_=user[0],
                        name=user[1],
                        email=user[2],
                        profile_pic=user[3],
                        corps_id=user[4]
                        )
            return user

    @classmethod
    async def create(cls, id_, name, email, profile_pic):
        # TODO send welcome message via Twilio
        pool = await get_db()
        async with pool.acquire() as conn:
            conn.execute("INSERT INTO user (id, name, email, profile_pic) "
                         "VALUES ($1, $2, $3, $4)",
                         id_, name, email, profile_pic)
        logger.info(f"User {name} successfully added to database.")

    @classmethod
    async def link_corps(cls, id_, corps_id):
        pool = await get_db()
        async with pool.acquire() as conn:
            conn.execute("UPDATE users SET corps_id = $1 WHERE id = $2", corps_id, id_)
        logger.info(f"User: {id_} successfully linked to {corps_id} corps.")

    @classmethod
    async def get_corps(cls):
        pool = await get_db()
        async with pool.acquire() as conn:
            divisions = await conn.fetch("SELECT id, name FROM divisions ORDER BY id")
            corps = await conn.fetch("SELECT id, name, div_id FROM corps ORDER BY id")
        return divisions, corps


class Recipients:
    @staticmethod
    async def create(name, phone):
        # TODO add html to add recipients
        pool = await get_db()
        async with pool.acquire() as conn:
            conn.execute("INSERT INTO recipients "
                         "(name, phone) "
                         "VALUES ($1, $2)", name, phone)
        logger.info(f"Recipient {name} successfully added to database.")

    @staticmethod
    async def get_groups():
        pool = await get_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name FROM groups")
        return rows

    @staticmethod
    async def get_recipients(group):
        recipients = []
        phone_nums = []
        pool = await get_db()
        async with pool.acquire() as conn:
            sql = ("SELECT r.name, r.phone "
                   "FROM recipients r "
                   "INNER JOIN recipient_groups rg on r.id = rg.recipient_id "
                   "WHERE rg.group_id = $1")
            rows = await conn.fetch(sql, group)
            for row in rows:
                recipients.append(row['name'])
                phone_nums.append(f"+1{row['phone']}")
            return recipients, phone_nums
