import requests
import json
import sqlite3
from flask import Flask, render_template, flash, request, url_for, redirect
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from oauthlib.oauth2 import WebApplicationClient
from wtforms import Form, TextAreaField, SelectField, validators
from twilio.rest import Client
from db import init_db_command
from user import User
from config import settings

# Flask Configuration
app = Flask(__name__)
app.config.from_object(__name__)
app.config["SECRET_KEY"] = settings['flask']['key']

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Google Configuration
google_client_id = settings['google']['id']
google_client_secret = settings['google']['secret']
google_discovery_url = "https://accounts.google.com/.well-known/openid-configuration"

# OAuth2 client setup
client = WebApplicationClient(google_client_id)

# database setup
try:
    init_db_command()
except sqlite3.OperationalError:
    # Assume it's already been created
    pass

# Flask-login helpfer to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

sid = settings['twilio']['sid']
token = settings['twilio']['token']
twilio = Client(sid, token)

choices = [("staff", "Staff"),
           ("students", "Students"),
           ("band", "Band"),
           ("songsters", "Songsters"),
           ("tester", "Debug")
           ]


class HomePage:
    @app.route("/")
    def index(self):
        if current_user.is_authenticated:
            # redirect to send_msg
            return (f"<p>Welcome {current_user.name} You're logged in!<br>"
                    f"Email: {current_user.email}</p>"
                    f"<div><img src='{current_user.profile_pic}'</img></div>"
                    f"<a class='button' href='/logout'>Log out</a>")
        else:
            return "<h2>St. Petersburg Text App</h2><a class='button' href='/login'>Google Login</a>"


def get_recipients(group):
    recipients = []
    phone_nums = []
    with open("data/contacts.json") as f:
        contacts = json.load(f)
        for person in contacts:
            if person[group]:
                recipients.append(person['name'])
                phone_nums.append(person['phone'])
    return recipients, phone_nums

class HomeForm(Form):
    group = SelectField("Recipients:", choices=choices)
    msg = TextAreaField("Message:", validators=[validators.required()])

    @app.route("/", methods=["GET", "POST"])
    def send_msg():
        form = HomeForm(request.form)
        print(form.errors)
        if request.method == "POST":
            if form.validate():
                group = request.form['group']
                message = request.form['msg']
                recipients, phone_nums = get_recipients(group)
                for phone_num in phone_nums:
                    twilio_msg = twilio.messages.create(to=phone_num,
                                                        from_=settings['twilio']['phone_num'],
                                                        body=message
                                                        )
                    print(twilio_msg)
                flash(f"Message sent to: {', '.join(recipients)}")
            else:
                flash("Error: All form fields are required.")
        return render_template("sendmsg.html", form=form)


if __name__ == "__main__":
    app.run(debug=True)
