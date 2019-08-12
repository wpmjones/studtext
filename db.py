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
    def __init__(self, id_, name, email, phone, profile_pic, corps_id, is_admin, is_approved):
        self.id = id_
        self.name = name
        self.email = email
        self.phone = phone
        self.profile_pic = profile_pic
        self.corps_id = corps_id
        self.is_admin = is_admin
        self.is_approved = is_approved

    @staticmethod
    def get(user_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                sql = (f"SELECT id, name, email, phone, profile_pic, corps_id, is_admin, is_approved "
                       f"FROM users WHERE id = %s")
                cursor.execute(sql, [user_id])
                user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user:
            return None
        user = User(id_=user[0],
                    name=user[1],
                    email=user[2],
                    phone=user[3],
                    profile_pic=user[4],
                    corps_id=user[5],
                    is_admin=user[6],
                    is_approved=user[7]
                    )
        return user

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
    def get_unapproved():
        with get_db() as conn:
            with conn.cursor() as cursor:
                sql = ("SELECT u.id, u.name, u.profile_pic, c.name as corps, d.name as div "
                       "FROM users u "
                       "INNER JOIN corps c ON u.corps_id = c.id "
                       "INNER JOIN divisions d ON c.div_id = d.id "
                       "WHERE is_approved = 0")
                cursor.execute(sql)
                users = cursor.fetchall()
        cursor.close()
        conn.close()
        return users

    @staticmethod
    def approve(user_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET is_approved = 1 WHERE id = %s "
                               "RETURNING id, name, email, phone, profile_pic, corps_id, is_admin, is_approved",
                               [user_id])
                fetch = cursor.fetchone()
                approved_user = User(id_=fetch[0],
                                     name=fetch[1],
                                     email=fetch[2],
                                     phone=fetch[3],
                                     profile_pic=fetch[4],
                                     corps_id=fetch[5],
                                     is_admin=fetch[6],
                                     is_approved=fetch[7]
                                     )
        cursor.close()
        conn.close()
        return approved_user

    @staticmethod
    def update_phone(id_, phone):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET phone = %s WHERE id = %s "
                               "RETURNING name", [id_, phone])
                user_name = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"{user_name}({id_}) successfully updated their phone number to {phone}")

    @staticmethod
    def link_corps(id_, corps_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
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
    def __init__(self, id_, name, phone, groups):
        self.id = id_
        self.name = name
        self.phone = phone
        self.groups = groups

    @staticmethod
    def create(name, phone):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO recipients "
                               "(name, phone) "
                               "VALUES (%s, %s) "
                               "RETURNING id", [name, phone])
                new_id = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"Recipient {name} successfully added to database.")
        return new_id

    @staticmethod
    def get(id_):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT name, phone "
                               "FROM recipients "
                               "WHERE id = %s",
                               [id_])
                recipient = cursor.fetchone()
                name = recipient[0]
                phone = recipient[1]
                cursor.execute("SELECT group_ID "
                               "FROM recipient_groups "
                               "WHERE recipient_id = %s", [id_])
                fetch = cursor.fetchall()
                groups = []
                for row in fetch:
                    groups.append(row[0])
                recipient = Recipients(
                    id_=id_,
                    name=name,
                    phone=phone,
                    groups=groups
                )
        cursor.close()
        conn.close()
        return recipient

    @staticmethod
    def update(id_, name, phone):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE recipients "
                               "SET name = %s, phone = %s "
                               "WHERE id = %s",
                               [name, phone, id_])
        cursor.close()
        conn.close()
        logger.info(f"Recipient {name} updated.")

    @staticmethod
    def assign_groups(recipient_id, group_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO recipient_groups (recipient_id, group_id) "
                               "VALUES (%s, %s)", [recipient_id, group_id])
        cursor.close()
        conn.close()

    @staticmethod
    def clear_groups(recipient_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM recipient_groups WHERE recipient_id = %s", [recipient_id])
        cursor.close()
        conn.close()

    @staticmethod
    def get_groups_by_user(corps_id):
        """This function pulls groups for a specified user"""
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name FROM groups "
                               "WHERE corps_id = %s "
                               "AND active = 1", [corps_id])
                groups = cursor.fetchall()
        cursor.close()
        conn.close()
        return groups

    @staticmethod
    def get_recipients(user_id):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT r.id, r.name, r.phone FROM recipients r "
                               "INNER JOIN users u on r.corps_id = u.corps_id "
                               "WHERE u.id = %s", [user_id])
                recipients = cursor.fetchall()
        cursor.close()
        conn.close()
        return recipients

    @staticmethod
    def get_recipients_by_group(group):
        """This function pulls recipients for a specified group"""
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

    @staticmethod
    def add_group(group_name, corps_id):
        """This function adds a group to the database"""
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO groups "
                               "(name, corps_id) "
                               "VALUES (%s, %s)", [group_name, corps_id])
        cursor.close()
        conn.close()

    @staticmethod
    def remove_group(group_id):
        """This function removes a group from the database"""
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE groups "
                               "SET active = 0 "
                               "WHERE id = %s", [group_id])
        cursor.close()
        conn.close()


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
