from quart import Quart, redirect, url_for, request, render_template, flash
from wtforms import Form, TextAreaField, SelectField, validators
from twilio.rest import Client
from config import settings

app = Quart(__name__)

# Set up Twilio
twilio = Client(settings['twilio']['sid'], settings['twilio']['token'])

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
async def index():
    return redirect(url_for("sendmsg"))


class HomeForm(Form):
    group = SelectField("Recipients:", choices=choices)
    msg = TextAreaField("Message:", validators=[validators.required()])


@app.route("/sendmsg", methods=["GET", "POST"])
async def sendmsg():
    form = HomeForm(request.form)
    return render_template("sendmsg.html", form=form)