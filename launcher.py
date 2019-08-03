import requests
import json
from datetime import datetime
from loguru import logger
from db import User, Recipients, Messages
from flask import Flask, redirect, url_for, request, render_template, flash, session
from oauthlib.oauth2 import WebApplicationClient
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, validators
from twilio.rest import Client
from config import settings

app = Flask(__name__)
app.secret_key = settings['flask']['key']

# Set up Twilio
twilio = Client(settings['twilio']['sid'], settings['twilio']['token'])

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Google Configuration
google_client_id = settings['google']['id']
google_client_secret = settings['google']['secret']
google_discovery_url = "https://accounts.google.com/.well-known/openid-configuration"

# OAuth2 client setup
client = WebApplicationClient(google_client_id)

# TODO Add favicon
# TODO can you add a bookmark link?


# Get Google Provider
def get_google_provider_cfg():
    return requests.get(google_discovery_url).json()


class HomeForm(FlaskForm):
    group = SelectField("Recipients:", coerce=int)
    msg = TextAreaField("Message:", validators=[validators.required()])


class DivisionForm(FlaskForm):
    divisions = User.get_divisions()
    division = SelectField("Division:", choices=divisions, coerce=int)


class CorpsForm(FlaskForm):
    corps = SelectField("Corps:", coerce=int)


# Flask-login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route("/protected")
@login_required
def protect():
    if current_user.is_authenticated:
        return (f"Logged in as: {current_user.name}\n"
                f"Assigned corps: {current_user.corps_id}\n"
                f"is_approved: {current_user.is_approved}")
    else:
        return render_template("login.html")


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("send_msg"))
    else:
        return render_template("login.html")


@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(authorization_endpoint,
                                             redirect_uri="https://satext.com/login/callback",
                                             scope=["openid", "email", "profile"])
    return redirect(request_uri)


@app.route("/logout")
@login_required
def logout():
    session.pop("alert", None)
    session.pop("corps", None)
    logout_user()
    return redirect(url_for("login"))


@app.route("/send_msg", methods=["GET", "POST"])
@login_required
def send_msg():
    # TODO need to test for approval as well as authenticated
    # TODO set up a way to handle responses
    # TODO set up initial message to new recipient (if recipient id not in messages database)
    if current_user.is_authenticated:
        form = HomeForm()
        form.group.choices = Recipients.get_groups(current_user.id)
        if request.method == "POST":
            group = request.form['group']
            message = request.form['msg']
            if group and message:
                logger.debug(f"{message} sending to group id {group}")
                recipients = Recipients.get_recipients(group)
                names = []
                for recipient in recipients:
                    names.append(recipient[0])
                    twilio_msg = twilio.messages.create(to=recipient[1],
                                                        from_=settings['twilio']['phone_num'],
                                                        body=message)
                    Messages.add_message(twilio_msg.sid, current_user.id, recipient[2], group, message)
                flash(f"Message sent to: {', '.join(names)}")
            else:
                flash("Error: All form fields are required.")
        if "alert" in session:
            flash(session["alert"])
            session.pop("alert", None)
        return render_template("sendmsg.html",
                               form=form,
                               choices=form.group.choices,
                               user_name=current_user.name,
                               profile_pic=current_user.profile_pic)
    else:
        return redirect(url_for("login"))


@app.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")
    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    # Prepare and send a request to get tokens! Yay tokens!
    url = "https" + request.url[4:]
    base_url = "https" + request.base_url[4:]
    token_url, headers, body = client.prepare_token_request(token_endpoint,
                                                            authorization_response=url,
                                                            redirect_url=base_url,
                                                            code=code)
    token_response = requests.post(token_url,
                                   headers=headers,
                                   data=body,
                                   auth=(google_client_id, google_client_secret))

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))
    # Now that you have tokens (yay) let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400
    # Check if user exists. If not, go to create page (to select corps)
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture)
        return redirect(url_for("select_corps"))
    user = User.get(unique_id)
    login_user(user)
    return redirect(url_for("send_msg"))


@app.route("/corps", methods=["GET", "POST"])
def select_corps():
    if current_user.is_authenticated:
        if request.method == "POST":
            if "division" in request.form:
                form = CorpsForm()
                form.corps.choices = User.get_corps(request.form['division'])
                return render_template("corps.html",
                                       form=form,
                                       corps=form.corps.choices,
                                       profile_pic=current_user.profile_pic)
            if "corps" in request.form:
                session["corps"] = User.link_corps(current_user.id, request.form['corps'])
                if not current_user.is_approved:
                    return redirect(url_for("approval"))
                session["alert"] = "You are now linked to a corps and can send messages."
                return redirect(url_for("send_msg"))
            else:
                flash("Error: Somethings has gone wrong. Please try  refreshing the page.")
        form = DivisionForm()
        return render_template("division.html",
                               form=form,
                               divisions=form.division.choices,
                               profile_pic=current_user.profile_pic)
    else:
        return redirect(url_for("login"))


@app.route("/approve")
def approve():
    if current_user.is_authenticated:
        # TODO check for is_admin
        return render_template("approve.html", users=User.get_unapproved())
    else:
        return redirect(url_for("login"))


@app.route("/yes")
def approve_user():
    if current_user.is_authenticated:
        user_id = request.args.get['uid']
        # TODO More to do here
        # Maybe check to see if there are any more unapproved users before going to send_msg
        return redirect(url_for("send_msg"))
    else:
        return redirect(url_for("login"))


@app.route("/approval")
def approval():
    if current_user.is_authenticated:
        user_name = current_user.name
        corps_name = session["corps"]
        body = f"{user_name} has requested access for {corps_name}. https://satext.com/approve"
        twilio_msg = twilio.messages.create(to="+16783797611",
                                            from_=settings['twilio']['phone_num'],
                                            body=body)
        Messages.add_message(twilio_msg.sid, "SYSTEM", 1, 0, body)
        return render_template("approval.html", name=current_user.name)
    else:
        return redirect(url_for("login"))


@app.route("/help")
def app_help():
    return render_template("help.html")


@app.route("/contact")
def contact_us():
    return render_template("contactus.html")
