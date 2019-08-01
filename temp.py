import quart.flask_patch
import asyncio
import requests
import json
from loguru import logger
from db import User, Recipients
from quart import Quart, redirect, url_for, request, render_template, flash
from oauthlib.oauth2 import WebApplicationClient
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, validators
from twilio.rest import Client
from config import settings

app = Quart(__name__)
app.config['SECRET_KEY'] = settings['flask']['key']

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

# Flask-login helpfer to retrieve a user from our db
@login_manager.user_loader
async def load_user(user_id):
    return await User.get(user_id)


# Get Google Provider
def get_google_provider_cfg():
    return requests.get(google_discovery_url).json()


@app.route("/")
async def index():
    return redirect(url_for("send_msg"))


class HomeForm(FlaskForm):
    loop = asyncio.get_event_loop()
    groups = loop.run_until_complete(Recipients.get_groups())
    groups = [[group['id'], group['name']] for group in groups]
    group = SelectField("Recipients:", choices=groups)
    msg = TextAreaField("Message:", validators=[validators.required()])


class CreateForm(FlaskForm):
    loop = asyncio.get_event_loop()
    divisions, corps = loop.run_until_complete(User.get_corps())
    divisions = [[div['id'], div['name']] for div in divisions]
    corps = [[crp['id'], crp['name'], crp['div_id']] for crp in corps]
    division = SelectField("Division:", choices=divisions)
    corps = SelectField("Corps:", choices=corps)


@app.route("/")
async def index():
    if current_user.is_authenticated:
        return redirect(url_for("send_msg"))
    else:
        return render_template("login.html")


@app.route("/login")
async def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(authorization_endpoint,
                                             redirect_uri=request.base_url + "/callback",
                                             scope=["openid", "email", "profile"])
    return redirect(request_uri)


@app.route("/logout")
@login_required
async def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/send_msg", methods=["GET", "POST"])
async def send_msg():
    if current_user.is_authenticated:
        form = HomeForm()
        if request.method == "POST":
            req_form = await request.form
            if req_form['group'] and req_form['msg']:
                group = req_form['group']
                message = req_form['msg']
                logger.debug(group, message)
                recipients, phone_nums = await Recipients.get_recipients(int(group))
                # TODO move messages to separate function
                # TODO log message to database
                for phone_num in phone_nums:
                    twilio_msg = twilio.messages.create(to=phone_num,
                                                        from_=settings['twilio']['phone_num'],
                                                        body=message)
                    logger.info(f"{twilio_msg.sid} sent to {', '.join(recipients)}")
                await flash(f"Message sent to: {', '.join(recipients)}")
            else:
                await flash("Error: All form fields are required.")
        return await render_template("sendmsg.html",
                                     form=form,
                                     choices=form.groups,
                                     profile_pic=current_user.profile_pic)
    else:
        return redirect(url_for("login"))


@app.route("/login/callback")
async def callback():
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
        await User.create(unique_id, users_name, users_email, picture)
        return redirect(url_for("create_user"))
    # Begin user session by logging the user in
    user = User.get(unique_id)
    login_user(user)
    # Send user back to homepage
    return redirect(url_for("send_msg"))


@app.route("/create")
async def create_user():
    if current_user.is_authenticated:
        form = CreateForm()
        if request.method == "POST":
            req_form = await request.form
            div_id = req_form['division']
            corps_id = req_form['corps']
            correct_div_id = form.corps[corps_id - 1][2]
            logger.debug(f"Selected division: {div_id} - Selected corps: {corps_id} - DivForThatCorps: {correct_div_id}")
            if div_id == correct_div_id:
                await User.link_corps(current_user.id, corps_id)
                return redirect(url_for("send_msg"))
            else:
                await flash("Error: Corps does not match the selected division.")
            return redirect(url_for("send_msg"))
        return await render_template("create.html",
                                     form=form,
                                     divisions=form.divisions,
                                     corps=form.corps,
                                     profile_pic=current_user.profile_pic)
    else:
        return redirect(url_for("login"))