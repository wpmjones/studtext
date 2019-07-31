import asyncio
import asyncpg
from config import settings
from flask import current_app, g
from flask.cli import with_appcontext
from flask_login import UserMixin

# database setup
@staticmethod
async def create_pool():
    pool = await asyncpg.create_pool(settings['pg']['uri'], max_size=15)
    return pool

loop = asyncio.get_event_loop()
conn = loop.run_until_complete(create_pool())

class User(UserMixin):
    def __init__(self, id_, name, email, profile_pic):
        # TODO add roles for users (who they can send to)
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic

    @staticmethod
    def get(user_id):
        user = await conn.fetchrow(f"SELECT * FROM user WHERE id = {user_id}")
        if not user:
            return None

        user = User(
            id_=user[0], name=user[1], email=user[2], profile_pic=user[3]
        )
        return user

    @staticmethod
    def create(id_, name, email, profile_pic, pool):
        # TODO send welcome message via Twilio
        conn = pool
        db.execute(
            "INSERT INTO user (id, name, email, profile_pic) "
            "VALUES (?, ?, ?, ?)",
            (id_, name, email, profile_pic),
        )
        db.commit()


class Receipients:
    @staticmethod
    def get():
        db = get_db()
        recipients = db.execute("SELECT * FROM recipients").fetchall()
        return recipients

    @staticmethod
    def create(name, phone, email, staff, students, band, songsters, womens_bible, home_league):
        # TODO add html to add recipients
        db = get_db()
        db.execute(
            "INSERT INTO recipients (name, phone, email, staff, students, band, songsters, womens_bible, home_league)"
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, phone, email, staff, students, band, songsters, womens_bible, home_league)
        )
        db.commit()

    @staticmethod
    def columns():
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM recipients")
        columns = [tuple[0] for tuple in cur.description]
        return columns
