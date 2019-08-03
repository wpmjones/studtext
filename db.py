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
    def __init__(self, id_, name, email, profile_pic, corps_id, is_admin, is_approved):
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic
        self.corps_id = corps_id
        self.is_admin = is_admin
        self.is_approved = is_approved

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
                    corps_id=user[4],
                    is_admin=user[5],
                    is_approved=user[6]
                    )
        return user

    @staticmethod
    def get_unapproved():
        with get_db() as conn:
            with conn.cursor() as cursor:
                sql = ("SELECT u.id, u.name, u.profile_pic, c.name as corps, d.name as div "
                       "FROM users u "
                       "INNER JOIN corps c ON u.corps_id = c.id "
                       "INNER JOIN divisions d ON c.div_id = d.id")
                cursor.execute(sql)
                users = cursor.fetchall()
        cursor.close()
        conn.close()
        return users

    @staticmethod
    def create(id_, name, email, profile_pic):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO users (id, name, email, profile_pic) "
                               "VALUES (%s, %s, %s, %s)",
                               [id_, name, email, profile_pic])
        cursor.close()
        conn.close()
        logger.info(f"User {name} successfully added to database.")

    @staticmethod
    def link_corps(id_, corps_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                logger.debug(cursor.mogrify("UPDATE users SET corps_id = %s WHERE id = %s", [corps_id, id_]))
                cursor.execute("UPDATE users SET corps_id = %s WHERE id = %s", [corps_id, id_])
                cursor.execute("SELECT name FROM corps WHERE id = %s", [corps_id])
                corps_name = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"User: {id_} successfully linked to {corps_name} corps.")
        return corps_name

    @staticmethod
    def get_divisions():
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM divisions WHERE id > 0 ORDER BY id")
                divisions = cursor.fetchall()
        cursor.close()
        conn.close()
        return divisions

    @staticmethod
    def get_corps(div_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM corps WHERE div_id = %s ORDER BY id", [div_id])
                corps = cursor.fetchall()
        cursor.close()
        conn.close()
        return corps


class Recipients:
    @staticmethod
    def create(name, phone):
        # TODO send welcome message via Twilio
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
    def get_groups(user_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT corps_id FROM users WHERE id = %s", [user_id])
                corps_id = cursor.fetchone()[0]
                cursor.execute("SELECT id, name FROM groups WHERE corps_id = %s", [corps_id])
                groups = cursor.fetchall()
        cursor.close()
        conn.close()
        return groups

    @staticmethod
    def get_recipients(group):
        with get_db() as conn:
            with conn.cursor() as cursor:
                sql = ("SELECT r.name, '+1' || r.phone as phone, r.id "
                       "FROM recipients r "
                       "INNER JOIN recipient_groups rg on r.id = rg.recipient_id "
                       "WHERE rg.group_id = %s")
                cursor.execute(sql, [group])
                recipients = cursor.fetchall()
        cursor.close()
        conn.close()
        return recipients


class Messages:
    @staticmethod
    def add_message(sid, user_id, recipient_id, group_id, message):
        with get_db() as conn:
            with conn.cursor() as cursor:
                sql = ("INSERT INTO messages "
                       "(sid, user_id, recipient_id, group_id, message) "
                       "VALUES (%s, %s, %s, %s, %s)")
                cursor.execute(sql, [sid, user_id, recipient_id, group_id, message])
        cursor.close()
        conn.close()
        logger.info(f"Twilio Message {sid} added to database.")
