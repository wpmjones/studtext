import requests
# import json
import sqlite3
from flask import Flask, render_template, flash, request, url_for, redirect
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from oauthlib.oauth2 import WebApplicationClient
# from wtforms import Form, TextAreaField, SelectField, validators
from twilio.rest import Client
from db import init_db_command, User, Receipients
from config import settings

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


# Get Google Provider
def get_google_provider_cfg():
    return requests.get(google_discovery_url).json()


sid = settings['twilio']['sid']
token = settings['twilio']['token']
twilio = Client(sid, token)

# This should come from the database
choices = [("students", "Students"),
           ("staff", "Staff"),
           ("band", "Band"),
           ("songsters", "Songsters"),
           ("womens_bible", "Women's Bible Study"),
           ("home_league", "Home League"),
           ("testers", "Debug"),
           ]


@app.route("/")
def hello():
    return "<h1 style='color:blue'>Hello There!</h1>"


if __name__ == "__main__":
    app.run(host="0.0.0.0")
