import asyncpg
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

    async def get(self, user_id):
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

    async def create(self, id_, name, email, profile_pic):
        # TODO send welcome message via Twilio
        pool = await get_db()
        async with pool.acquire() as conn:
            conn.execute("INSERT INTO user (id, name, email, profile_pic) "
                         "VALUES ($1, $2, $3, $4)",
                         id_, name, email, profile_pic)


class Receipients:
    @staticmethod
    async def create(name, phone):
        # TODO add html to add recipients
        pool = await get_db()
        async with pool.acquire() as conn:
            conn.execute("INSERT INTO recipients"
                         "(name, phone, email, staff, students, band, songsters, womens_bible, home_league)"
                         "VALUES ($1, $2)", name, phone)

    @staticmethod
    async def get_groups():
        pool = await get_db()
        async with pool.acquire() as conn:
            sql = "SELECT id, name FROM groups"
            rows = await conn.fetch(sql)
            return rows

    @staticmethod
    async def get_recipients(group):
        recipients = []
        phone_nums = []
        pool = await get_db()
        async with pool.acquire() as conn:
            sql = ("SELECT r.name, r.phone"
                   "FROM recipients r"
                   "INNER JOIN recipient_groups rg on r.id = rg.id"
                   "WHERE rg.group_id = $1")
            rows = await conn.fetch(sql, group)
            for row in rows:
                recipients.append(row['name'])
                phone_nums.append(f"+1{row['phone']}")
            return recipients, phone_nums
