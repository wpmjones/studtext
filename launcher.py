import requests
import json
import asyncpg
from flask import Flask, render_template, flash, request, url_for, redirect
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from oauthlib.oauth2 import WebApplicationClient
from wtforms import Form, TextAreaField, SelectField, validators
from twilio.rest import Client
from db import Psql, User, Receipients
from config import settings

# Quart Configuration
app = Quart(__name__)
app.config.from_object(__name__)
app.secret_key = settings['flask']['key']

@app.before_serving
async def startup():
    app.pool = await asyncpg.create_pool(settings['pg']['uri'], max_size=15)

@app.after_serving
async def shutdown():
    await app.pool.close()

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Google Configuration
google_client_id = settings['google']['id']
google_client_secret = settings['google']['secret']
google_discovery_url = "https://accounts.google.com/.well-known/openid-configuration"

# OAuth2 client setup
client = WebApplicationClient(google_client_id)


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
def index():
    if current_user.is_authenticated:
        # return (f"<p>Welcome {current_user.name} You're logged in!<br>"
        #         f"Email: {current_user.email}</p>"
        #         f"<div><img src='{current_user.profile_pic}'</img></div>"
        #         f"<a class='btn btn-default' href='/logout' role='button'>Log out</a>")
        return redirect(url_for("sendmsg"))
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
                                             redirect_uri=request.base_url + "/callback",
                                             scope=["openid", "email", "profile"],
                                             )
    return redirect(request_uri)

@app.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")
    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    # Prepare and send a request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(token_endpoint,
                                                            authorization_response=request.url,
                                                            redirect_url=request.base_url,
                                                            code=code
                                                            )
    token_response = requests.post(token_url,
                                   headers=headers,
                                   data=body,
                                   auth=(google_client_id, google_client_secret)
                                   )

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
    # Create a user in your db with the information provided
    # by Google
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture)
    # Begin user session by logging the user in
    login_user(user)
    # Send user back to homepage
    return redirect(url_for("sendmsg"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


def get_recipients(group):
    recipients = []
    phone_nums = []
    groups = Receipients.columns()
    element = groups.index(group)
    full_list = Receipients.get()
    for recipient in full_list:
        if recipient[element]:
            recipients.append(recipient[groups.index("name")])
            phone_nums.append(recipient[groups.index("phone")])
    return recipients, phone_nums


class HomeForm(Form):
    group = SelectField("Recipients:", choices=choices)
    msg = TextAreaField("Message:", validators=[validators.required()])

    @app.route("/sendmsg", methods=["GET", "POST"])
    def sendmsg():
        if current_user.is_authenticated:
            form = HomeForm(request.form)
            print(form.errors)
            profile_pic = current_user.profile_pic
            if request.method == "POST":
                if form.validate():
                    group = request.form['group']
                    message = request.form['msg']
                    recipients, phone_nums = get_recipients(group)
                    # TODO move messages to separate function
                    # TODO log message to database
                    for phone_num in phone_nums:
                        twilio_msg = twilio.messages.create(to=phone_num,
                                                            from_=settings['twilio']['phone_num'],
                                                            body=message
                                                            )
                        print(twilio_msg)
                    flash(f"Message sent to: {', '.join(recipients)}")
                else:
                    flash("Error: All form fields are required.")
            # TODO figure out how to set up options in sendmgs.html from Receipients.columns()
            return render_template("sendmsg.html", form=form, profile_pic=profile_pic)
        else:
            return ("<h2>St. Petersburg Text App</h2>"
                    "<a class='btn btn-default' href='/login' role='button'>Google Login</a>")


if __name__ == "__main__":
    app.run(host="0.0.0.0")
