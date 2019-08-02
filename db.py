import psycopg2
from loguru import logger
from flask_login import UserMixin
from config import settings


def get_db():
    conn = psycopg2.connect(host="localhost",
                            dbname=settings['pg']['dbname'],
                            user=settings['pg']['user'],
                            password=settings['pg']['password'])
    conn.set_session(autocommit=True)
    return conn


class User(UserMixin):
    def __init__(self, id_, name, email, profile_pic, corps_id):
        # TODO add roles for users (who they can send to)
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic
        self.corps_id = corps_id

    @staticmethod
    def get(user_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                sql = f"SELECT * FROM users WHERE id = %s"
                cursor.execute(sql, [user_id])
                user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user:
            return None
        user = User(id_=user[0],
                    name=user[1],
                    email=user[2],
                    profile_pic=user[3],
                    corps_id=user[4]
                    )
        return user

    @staticmethod
    def create(id_, name, email, profile_pic):
        # TODO send welcome message via Twilio
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO user (id, name, email, profile_pic) "
                               "VALUES (%s, %s, %s, %s)",
                               [id_, name, email, profile_pic])
        cursor.close()
        conn.close()
        logger.info(f"User {name} successfully added to database.")

    @staticmethod
    def link_corps(id_, corps_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET corps_id = %d WHERE id = %s", [corps_id, id_])
                cursor.execute("SELECT name FROM corps WHERE corps_id = %d", [corps_id])
                corps_name = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"User: {id_} successfully linked to {corps_name} corps.")

    @staticmethod
    def get_corps():
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM divisions ORDER BY id")
                divisions = cursor.fetchall()
                cursor.execute("SELECT id, name, div_id FROM corps ORDER BY id")
                corps = cursor.fetchall()
        cursor.close()
        conn.close()
        return divisions, corps


class Recipients:
    @staticmethod
    def create(name, phone):
        # TODO add html to add recipients
        with get_db() as conn:
            with conn.cursor() as cursor:
                conn.execute("INSERT INTO recipients "
                             "(name, phone) "
                             "VALUES (%s, %s)", [name, phone])
        cursor.close()
        conn.close()
        logger.info(f"Recipient {name} successfully added to database.")

    @staticmethod
    def get_groups():
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM groups")
                groups = cursor.fetchall()
        cursor.close()
        conn.close()
        return groups

    @staticmethod
    def get_recipients(group):
        recipients = []
        phone_nums = []
        with get_db() as conn:
            with conn.cursor() as cursor:
                sql = ("SELECT r.name, r.phone "
                       "FROM recipients r "
                       "INNER JOIN recipient_groups rg on r.id = rg.recipient_id "
                       "WHERE rg.group_id = %d")
                rows = cursor.execute(sql, [group])
                for row in rows:
                    recipients.append(row[0])
                    phone_nums.append(f"+1{row[1]}")
            return recipients, phone_nums
