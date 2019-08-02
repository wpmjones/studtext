import quart.flask_patch

import requests
import json
from loguru import logger
from flask_login import LoginManager, current_user, login_required, login_user, logout_user, UserMixin
from quart import Quart, redirect, request, url_for, render_template
from oauthlib.oauth2 import WebApplicationClient
from config import settings

app = Quart(__name__)
app.secret_key = settings['flask']['key']
login_manager = LoginManager()
login_manager.init_app(app)

# Google Configuration
google_client_id = settings['google']['id']
google_client_secret = settings['google']['secret']
google_discovery_url = "https://accounts.google.com/.well-known/openid-configuration"


# Get Google Provider
def get_google_provider_cfg():
    logger.debug("start get_google_provider_cfg")
    return requests.get(google_discovery_url).json()


# OAuth2 client setup
client = WebApplicationClient(google_client_id)

# Rather than storing passwords in plaintext, use something like
# bcrypt or similar to store the password hash.
users = {'quart': {'password': 'secret'}}


class User(UserMixin):
    pass


@login_manager.user_loader
def user_loader(username):
    if username not in users:
        return
    user = User()
    user.id = username
    return user


@app.route("/")
async def index():
    logger.debug("start index route")
    logger.debug(current_user)
    if current_user.is_authenticated:
        logger.debug("Current user is authenticated")
        return redirect(url_for("protected"))
    else:
        logger.debug("Current user is not authenticated")
        return await render_template("login.html")


@app.route('/', methods=['GET', 'POST'])
async def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(authorization_endpoint,
                                             redirect_uri=request.base_url + "/callback",
                                             scope=["openid", "email", "profile"])
    return redirect(request_uri)


@app.route("/login/callback")
async def callback():
    logger.debug("start callback route")
    code = request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = client.prepare_token_request(token_endpoint,
                                                            authorization_response=request.url,
                                                            redirect_url=request.base_url,
                                                            code=code)
    token_response = requests.post(token_url,
                                   headers=headers,
                                   data=body,
                                   auth=(google_client_id, google_client_secret))
    client.parse_request_body_response(json.dumps(token_response.json()))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    if not userinfo_response.json().get("email_verified"):
        return "User email not available or not verified by Google.", 400
    return redirect(url_for("protected"))


@app.route('/protected')
@login_required
async def protected():
    return 'Logged in as: ' + current_user.id


@app.route('/logout')
async def logout():
    logout_user()
    return 'Logged out'


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('login'))
