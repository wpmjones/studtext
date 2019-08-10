import requests
import json
import phonenumbers
from loguru import logger
from db import User, Recipients, Messages
from flask import Flask, redirect, url_for, request, render_template, flash, session
from oauthlib.oauth2 import WebApplicationClient
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, validators, ValidationError
from twilio.rest import Client
from config import settings

app = Flask(__name__)
app.secret_key = settings["flask"]["key"]

# Set up Twilio
twilio = Client(settings["twilio"]["sid"], settings["twilio"]["token"])

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/login"

# Google Configuration
google_client_id = settings["google"]["id"]
google_client_secret = settings["google"]["secret"]
google_discovery_url = "https://accounts.google.com/.well-known/openid-configuration"

# OAuth2 client setup
client = WebApplicationClient(google_client_id)

# TODO can you add a bookmark link?


# Get Google Provider
def get_google_provider_cfg():
    return requests.get(google_discovery_url).json()


class MessageForm(FlaskForm):
    group = SelectField("Recipients:", coerce=int)
    msg = TextAreaField("Message:", validators=[validators.DataRequired()])


class MenuForm(FlaskForm):
    actions = SelectField("Actions:", coerce=int)


class DivisionForm(FlaskForm):
    divisions = User.get_divisions()
    division = SelectField("Division:", choices=divisions, coerce=int)


class CorpsForm(FlaskForm):
    corps = SelectField("Corps:", coerce=int)


class SingleSelectForm(FlaskForm):
    select = SelectField(coerce=int)


class AddForm(FlaskForm):
    name = StringField('Username', validators=[validators.DataRequired()])
    phone = StringField('Phone', validators=[validators.DataRequired()])

    def validate_phone(form, field):
        if len(field.data) > 16:
            raise ValidationError('Invalid phone number.')
        try:
            input_number = phonenumbers.parse(field.data)
            if not (phonenumbers.is_valid_number(input_number)):
                raise ValidationError('Invalid phone number.')
        except:
            input_number = phonenumbers.parse("+1"+field.data)
            if not (phonenumbers.is_valid_number(input_number)):
                raise ValidationError('Invalid phone number.')


class GroupForm(FlaskForm):
    groups = SelectMultipleField("Groups:", coerce=int)

# Flask-login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


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
        return redirect(url_for("user_select_corps"))
    user = User.get(unique_id)
    login_user(user)
    return redirect(url_for("send_msg"))


@app.route("/logout")
@login_required
def logout():
    session.pop("alert", None)
    session.pop("corps", None)
    logout_user()
    return redirect(url_for("login"))


@app.route("/protected")
@login_required
def protect():
    return (f"Logged in as: {current_user.name}<br />"
            f"Assigned corps: {current_user.corps_id}<br />"
            f"is_approved: {current_user.is_approved}")


@app.route("/send_msg", methods=["GET", "POST"])
@login_required
def send_msg():
    """Main page used for sending messages to groups"""
    # TODO set up a way to handle responses
    # TODO set up initial message to new recipient (if recipient id not in messages database)
    if current_user.is_approved:
        form = MessageForm()
        form.group.choices = Recipients.get_groups(current_user.id)
        if request.method == "POST":
            group = request.form["group"]
            message = request.form["msg"]
            if group and message:
                recipients = Recipients.get_recipients_by_group(group)
                names = []
                logger.debug(f"{message} sending to group id {group}")
                for recipient in recipients:
                    names.append(recipient[0])
                    twilio_msg = twilio.messages.create(to=recipient[1],
                                                        from_=settings["twilio"]["phone_num"],
                                                        body=message)
                    Messages.add_message(twilio_msg.sid, current_user.id, recipient[2], group, message)
                flash(f"Message sent to: {', '.join(names)}", "Success")
            else:
                flash("All form fields are required.", "Error")
        if "alert" in session:
            flash(session["alert"][0], session["alert"][1])
            session.pop("alert", None)
        return render_template("sendmsg.html",
                               form=form,
                               choices=form.group.choices,
                               user_name=current_user.name,
                               profile_pic=current_user.profile_pic)
    else:
        return render_template("approval.html", name=current_user.name)


@app.route("/corps", methods=["GET", "POST"])
@login_required
def user_select_corps():
    """This is where a user selects the corps they are associated with"""
    if request.method == "POST":
        if "division" in request.form:
            form = CorpsForm()
            form.corps.choices = User.get_corps(request.form["division"])
            return render_template("corps.html",
                                   form=form,
                                   corps=form.corps.choices,
                                   profile_pic=current_user.profile_pic)
        if "corps" in request.form:
            session["corps"] = User.link_corps(current_user.id, request.form["corps"])
            if not current_user.is_approved:
                return redirect(url_for("approval"))
            session["alert"] = ("You are now linked to a corps and can send messages.", "Success")
            return redirect(url_for("send_msg"))
        else:
            flash("Something has gone wrong. Please try  refreshing the page.", "Error")
    form = DivisionForm()
    return render_template("division.html",
                           form=form,
                           divisions=form.division.choices,
                           profile_pic=current_user.profile_pic)


@app.route("/approve")
@login_required
def approve():
    """This is an admin only page that lists users needed approval"""
    if current_user.is_admin:
        return render_template("approve.html", users=User.get_unapproved())
    else:
        return redirect(url_for("send_msg"))


@app.route("/yes")
@login_required
def approve_user():
    """This is an admin only page where the user is actually approved"""
    if current_user.is_admin:
        # Approve this user in the database
        User.approve(request.args.get["uid"])
        # Check if there are more unapproved users
        if len(User.get_unapproved()) > 0:
            return redirect(url_for("approve"))
        else:
            return redirect(url_for("send_msg"))
    else:
        return redirect(url_for("send_msg"))


@app.route("/approval")
@login_required
def approval():
    """This page alerts the admin of a new user and tells the user they must wait for approval"""
    user_name = current_user.name
    corps_name = session["corps"]
    body = f"{user_name} has requested access for {corps_name}. https://satext.com/approve"
    twilio_msg = twilio.messages.create(to="+16783797611",
                                        from_=settings["twilio"]["phone_num"],
                                        body=body)
    Messages.add_message(twilio_msg.sid, "SYSTEM", 1, 0, body)
    return render_template("approval.html", name=current_user.name)


@app.route("/menu", methods=["GET", "POST"])
@login_required
def menu():
    """This page is designed to let the user select additional actions"""
    form = MenuForm(request.form)
    if request.method == "POST":
        if request.form["actions"] == "1":
            return redirect(url_for("add_recipient"))
        if request.form["actions"] == "2":
            return redirect(url_for("select_recipient"))
        if request.form["actions"] == "3":
            # TODO create function for add_group
            return redirect(url_for("add_group"))
        if request.form["actions"] == "4":
            # TODO create function for remove_group
            return redirect(url_for("remove_group"))
        flash("Please select an item from the list.", "Error")
    else:
        return render_template("menu.html",
                               form=form,
                               profile_pic=current_user.profile_pic)


@app.route("/addrecipient", methods=["GET", "POST"])
@login_required
def add_recipient():
    """This page allows a user to add a new recipient for their corps"""
    form = AddForm(request.form)
    if request.method == "POST":
        logger.debug("POST")
    if form.validate():
        logger.debug("Validated")
    logger.debug("Pre-if")
    if request.method == "POST" and form.validate():
        logger.debug("Post-if")
        if request.form["phone"] and request.form["name"]:
            logger.debug("Inside if phone/name")
            session["new_name"] = request.form["name"]
            session["new_phone"] = request.form["phone"]
            session["recipient_id"] = Recipients.create(request.form["name"], request.form["phone"])
            welcome_message(session["recipient_id"], request.form["name"], request.form["phone"])
            return redirect(url_for("manage_recipient"))
        else:
            flash("All form fields are required.", "Error")
    else:
        return render_template("addrecipient.html",
                               form=form,
                               profile_pic=current_user.profile_pic)


@app.route("/removerecipient", methods=["GET", "POST"])
@login_required
def remove_recipient():
    """This page allows a user to remove a recipient from their corps"""
    # TODO Finish this function
    if request.method == "POST":
        pass
    else:
        form = SingleSelectForm()
        form.select.choices = Recipients.get_recipients(current_user.id)


@app.route("/selectrecipient", methods=["GET", "POST"])
@login_required
def select_recipient():
    """This page allows the user to select a recipient for modification"""
    if request.method == "POST":
        session["recipient_id"] = request.form["recipient"]
        # TODO get groups from db and add to session before redirect
        return redirect(url_for("manage_recipient"))
    else:
        form = SingleSelectForm()
        form.select.choices = Recipients.get_recipients(current_user.id)
        return render_template("selectrecipient.html",
                               form=form,
                               recipients=form.select.choices,
                               profile_pic=current_user.profile_pic)


@app.route("/managerecipient", methods=["GET", "POST"])
@login_required
def manage_recipient():
    """This page allows the user to modify the selected recipient (name, phone, and groups)."""
    if request.method == "POST":
        if request.form["name"] != session["new_name"] or request.form["phone"] != session["new_phone"]:
            Recipients.update(session["recipient_id"], request.form["name"], request.form["phone"])
        Recipients.assign_groups(session["new_id"], request.form["groups"])
        session["alert"] = f"{session['new_name']} is now attached to the selected groups."
        session.pop("new_id", None)
        session.pop("new_name", None)
        session.pop("new_phone", None)
        return redirect(url_for("send_msg"))
    else:
        form = GroupForm()
        form.groups.choices = Recipients.get_groups(current_user.id)
        return render_template("managerecipient.html",
                               form=form,
                               groups=form.groups.choices,
                               profile_pic=current_user.profile_pic,
                               recipient=session["new_name"],
                               phone=session["phone"])


@app.route("/help")
def app_help():
    return render_template("help.html")


@app.route("/contact")
def contact_us():
    return render_template("contactus.html")

def welcome_message(recipient_id, name, phone):
    body = (f"Welcome {name}! You've been added to a group for Salvation Army text messages. "
           f"If you have questions, talk to your corps officers. Text 'STOP' to cancel messages.")
    twilio_msg = twilio.messages.create(to="+1" + phone,
                                        from_=settings["twilio"]["phone_num"],
                                        body=body)
    Messages.add_message(twilio_msg.sid, "WELCOME", recipient_id, 0, body)