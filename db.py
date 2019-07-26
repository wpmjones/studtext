# http://flask.pocoo.org/docs/1.0/tutorial/database/
import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext
from flask_login import UserMixin


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            "sqlite_db", detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


class User(UserMixin):
    def __init__(self, id_, name, email, profile_pic):
        # TODO add roles for users (who they can send to)
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic

    @staticmethod
    def get(user_id):
        db = get_db()
        user = db.execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return None

        user = User(
            id_=user[0], name=user[1], email=user[2], profile_pic=user[3]
        )
        return user

    @staticmethod
    def create(id_, name, email, profile_pic):
        # TODO send welcome message via Twilio
        db = get_db()
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
