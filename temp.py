import requests
import json
import sqlite3
from flask import Flask, render_template, flash, request, url_for, redirect
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from oauthlib.oauth2 import WebApplicationClient
from wtforms import Form, TextAreaField, SelectField, validators
from twilio.rest import Client
from db import init_db_command, User, Receipients
from config import settings

app = Flask(__name__)
app.config.from_object(__name__)
app.config["SECRET_KEY"] = settings['flask']['key']


@app.route("/")
def hello():
    return "<h1 style='color:blue'>Hello There!</h1>"


if __name__ == "__main__":
    app.run(host="0.0.0.0")
