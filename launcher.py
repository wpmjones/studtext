import quart.flask_patch

import requests
from secrets import compare_digest
from loguru import logger
from flask_login import LoginManager, current_user, login_required, login_user, logout_user, UserMixin
from quart import Quart, redirect, request, url_for
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


@app.route('/', methods=['GET', 'POST'])
async def login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = client.prepare_request_uri(authorization_endpoint,
                                             redirect_uri=request.base_url + "/callback",
                                             scope=["openid", "email", "profile"])
    logger.debug(request_uri)
    if request.method == 'GET':
        return '''
               <form method='POST'>
                <input type='text' name='username' id='username' placeholder='username'></input>
                <input type='password' name='password' id='password' placeholder='password'></input>
                <input type='submit' name='submit'></input>
               </form>
               '''

    username = (await request.form)['username']
    password = (await request.form)['password']
    if username in users and compare_digest(password, users[username]['password']):
        user = User()
        user.id = username
        login_user(user)
        return redirect(url_for('protected'))

    return 'Bad login'


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
