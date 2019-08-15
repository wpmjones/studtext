import requests
import json
from loguru import logger
from db import User, Recipients, Messages
from utils import welcome_recipient, welcome_user, discord_log
from flask import Flask, redirect, url_for, request, render_template, flash, session
from oauthlib.oauth2 import WebApplicationClient
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, validators
from twilio.twiml.messaging_response import MessagingResponse
from twilio.base.exceptions import TwilioRestException
from config import settings, twilio

app = Flask(__name__)
app.secret_key = settings["flask"]["key"]


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

# Send logs to discord
logger.add(discord_log, level="DEBUG")

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


class SingleTextForm(FlaskForm):
    text_field = StringField(validators=[validators.DataRequired()])


class SingleSelectForm(FlaskForm):
    select = SelectField(coerce=int)


class AddRecipientForm(FlaskForm):
    name = StringField("Username", validators=[validators.DataRequired()])
    phone = StringField("Phone", validators=[validators.DataRequired()])


class AddGroupForm(FlaskForm):
    grp = StringField("Group Name:", validators=[validators.DataRequired()])


class GroupForm(FlaskForm):
    groups = SelectMultipleField("Groups:", coerce=int)

# Flask-login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route("/sms", methods=["GET", "POST"])
def incoming_sms():
    """Respond to incoming sms"""
    resp = MessagingResponse()
    resp.message = "At this time, SA Text does not support SMS responses. But in the future, we hope to do so!"
    logger.info("Message received")
    return str(resp)


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
    # return search_twilio_numbers(twilio, "434")


@app.route("/send_msg", methods=["GET", "POST"])
@login_required
def send_msg():
    """Main page used for sending messages to groups"""
    # TODO set up a way to handle responses
    if current_user.is_approved:
        form = MessageForm(request.form)
        form.group.choices = Recipients.get_groups_by_user(current_user.corps_id)
        if request.method == "POST":
            group = request.form["group"]
            message = request.form["msg"]
            if group and message:
                if "corps_phone" not in session:
                    session["corps_phone"] = User.get_corps_phone(current_user.corps_id)
                recipients = Recipients.get_recipients_by_group(group)
                names = []
                logger.debug(f"{message} sending to group id {group}")
                for recipient in recipients:
                    names.append(recipient[0])
                    twilio_msg = twilio.messages.create(to=recipient[1],
                                                        from_=session["corps_phone"],
                                                        body=message)
                    Messages.add_message(twilio_msg.sid, current_user.id, recipient[2], group, message)
                flash(f"Message sent to: {', '.join(names)}", "Success")
            else:
                flash("All form fields are required.", "Error")
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
                return redirect(url_for("user_add_phone"))
            return redirect(url_for("send_msg"))
        else:
            flash("Something has gone wrong. Please try  refreshing the page.", "Error")
    form = DivisionForm()
    return render_template("division.html",
                           form=form,
                           divisions=form.division.choices,
                           profile_pic=current_user.profile_pic)


@app.route("/userphone", methods=["GET", "POST"])
@login_required
def user_add_phone():
    """This is where a user provides their phone number"""
    form = SingleTextForm(request.form)
    if request.method == "POST":
        try:
            number_info = twilio.lookups.phone_numbers(form.text_field.data).fetch()
            new_phone = number_info.phone_number[2:]
            logger.debug(new_phone)
        except TwilioRestException:
            flash("Invalid phone number", "Error")
            return render_template("updatephone.html",
                                   form=form,
                                   profile_pic=current_user.profile_pic)
        User.update_phone(current_user.id, new_phone)
        if not current_user.is_approved:
            return redirect(url_for("approval"))
        return redirect(url_for("send_msg"))
    form.text_field.label = "Phone:"
    return render_template("updatephone.html",
                           form=form,
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
        if request.method == "GET":
            # Approve this user in the database
            approved_user = User.approve(request.args.get("uid"))
            corps_phone = User.get_corps_phone(approved_user.corps_id)
            response = welcome_user(approved_user.id, approved_user.name, f"+1{approved_user.phone}", corps_phone)
            Messages.add_message(*response)
            # Check if there are more unapproved users
            if len(User.get_unapproved()) > 0:
                return redirect(url_for("approve"))
            else:
                return redirect(url_for("send_msg"))
        else:
            return redirect(url_for("approve"))
    else:
        return redirect(url_for("send_msg"))


@app.route("/approval")
@login_required
def approval():
    """This page alerts the admin of a new user and tells the user they must wait for approval"""
    user_name = current_user.name
    corps_name = session["corps"]
    body = f"{user_name} has requested access for {corps_name}. https://satext.com/approve"
    twilio_msg = twilio.messages.create(to=settings["twilio"]["admin_num"],
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
            return redirect(url_for("add_group"))
        if request.form["actions"] == "4":
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
    form = AddRecipientForm(request.form)
    if request.method == "POST":
        if request.form["phone"] and request.form["name"]:
            try:
                number_info = twilio.lookups.phone_numbers(request.form["phone"]).fetch()
                session["new_phone"] = number_info.phone_number[2:]
            except TwilioRestException:
                flash("Invalid phone number", "Error")
                return render_template("addrecipient.html",
                                       form=form,
                                       profile_pic=current_user.profile_pic)
            session["new_name"] = request.form["name"]
            session["recipient_id"] = Recipients.create(request.form["name"],
                                                        session["new_phone"],
                                                        current_user.corps_id)
            if "corps_phone" not in session:
                session["corps_phone"] = User.get_corps_phone(current_user.corps_id)
            response = welcome_recipient(session["recipient_id"], request.form["name"],
                                         number_info.phone_number, session["corps_phone"])
            Messages.add_message(*response)
            logger.info(f"New recipient ({session['recipient_id']}) added to the database by "
                        f"{current_user.name}({current_user.id})")
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
    form = SingleSelectForm(request.form)
    if request.method == "POST":
        pass
    else:
        form.select.choices = Recipients.get_recipients(current_user.id)


@app.route("/addgroup", methods=["GET", "POST"])
@login_required
def add_group():
    """This page allows a user to add a new group for their corps"""
    form = AddGroupForm(request.form)
    if request.method == "POST":
        if form.grp.data:
            Recipients.add_group(form.grp.data, current_user.corps_id)
            flash(f"{form.grp.data} added to the database.")
            logger.info(f"New group ({form.grp.data}) added to the database by "
                        f"{current_user.name}({current_user.id})")
            return redirect(url_for("send_msg"))
        else:
            flash("All form fields are required.", "Error")
    else:
        return render_template("addgroup.html",
                               form=form,
                               profile_pic=current_user.profile_pic)


@app.route("/removegroup", methods=["GET", "POST"])
@login_required
def remove_group():
    form = SingleSelectForm(request.form)
    if request.method == "POST":
        Recipients.remove_group(form.select.data)
        flash("Group removed from the database")
        logger.info(f"Group ({form.select.data}) set as inactive in the database by "
                    f"{current_user.name}({current_user.id})")
        return redirect(url_for("send_msg"))
    else:
        form.select.choices = Recipients.get_groups_by_user(current_user.corps_id)
        form.select.label = "Group to Remove:"
        return render_template("removegroup.html",
                               form=form,
                               profile_pic=current_user.profile_pic)


@app.route("/selectrecipient", methods=["GET", "POST"])
@login_required
def select_recipient():
    """This page allows the user to select a recipient for modification"""
    form = SingleSelectForm(request.form)
    if request.method == "POST":
        selected_recipient = Recipients.get(int(request.form["recipient"]))
        session["recipient_id"] = selected_recipient.id
        session["new_name"] = selected_recipient.name
        session["new_phone"] = selected_recipient.phone
        session["groups"] = selected_recipient.groups
        return redirect(url_for("manage_recipient"))
    else:
        form.select.choices = Recipients.get_recipients(current_user.id)
        return render_template("selectrecipient.html",
                               form=form,
                               recipients=form.select.choices,
                               profile_pic=current_user.profile_pic)


@app.route("/managerecipient", methods=["GET", "POST"])
@login_required
def manage_recipient():
    """This page allows the user to modify the selected recipient (name, phone, and groups)."""
    form = GroupForm(request.form)
    if request.method == "POST":
        if request.form["name"] != session["new_name"] or request.form["phone"] != session["new_phone"]:
            Recipients.update(session["recipient_id"], request.form["name"], request.form["phone"])
        Recipients.clear_groups(session["recipient_id"])
        for group_id in form.groups.data:
            try:
                logger.debug(group_id)
                Recipients.assign_groups(session["recipient_id"], group_id)
            except:
                logger.exception("Failure on assign_groups")
        logger.info(f"Added recipient {session['recipient_id']} to groups {form.groups.data}")
        flash(f"{session['new_name']} is now attached to the selected groups.", "Success")
        session.pop("recipient_id", None)
        session.pop("new_name", None)
        session.pop("new_phone", None)
        if "groups" in session:
            session.pop("groups", None)
        return redirect(url_for("send_msg"))
    else:
        if "groups" in session:
            selected = session["groups"]
        else:
            selected = ["None"]
        form.groups.choices = Recipients.get_groups_by_user(current_user.corps_id)
        return render_template("managerecipient.html",
                               form=form,
                               groups=form.groups.choices,
                               profile_pic=current_user.profile_pic,
                               recipient=session["new_name"],
                               phone=session["new_phone"],
                               selected=selected)


@app.route("/help")
def app_help():
    return render_template("help.html")


@app.route("/contact", methods=["GET", "POST"])
@login_required
def contact_us():
    form = MessageForm(request.form)
    if request.method == "POST":
        twilio_msg = twilio.messages.create(to=settings["twilio"]["admin_num"],
                                            from_=settings["twilio"]["phone_num"],
                                            body="New contact us form completed.")
        Messages.add_message(twilio_msg.sid, current_user.id, 0, 0, form.msg.data)
        flash("Your message has been received. We'll get back to you soon!")
        logger.info(f"Contact form submitted by {current_user.name} ({current_user.id})")
        # TODO create page for reviewing contact forms
        return redirect(url_for("send_msg"))
    else:
        return render_template("contactus.html",
                               form=form,
                               profile_pic=current_user.profile_pic)
