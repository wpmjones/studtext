import quart.flask_patch
import asyncio
from loguru import logger
from db import User, Recipients
from quart import Quart, redirect, url_for, request, render_template, flash
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, validators
from twilio.rest import Client
from config import settings

app = Quart(__name__)
app.config['SECRET_KEY'] = settings['flask']['key']

# Set up Twilio
twilio = Client(settings['twilio']['sid'], settings['twilio']['token'])


@app.route("/")
async def index():
    return redirect(url_for("sendmsg"))

loop = asyncio.get_event_loop()
groups = loop.run_until_complete(Recipients.get_groups())
choices = [[group['id'], group['name']] for group in groups]


class HomeForm(FlaskForm):
    group = SelectField("Recipients:", choices=choices)
    msg = TextAreaField("Message:", validators=[validators.required()])


@app.route("/sendmsg", methods=["GET", "POST"])
async def sendmsg():
    form = HomeForm()
    if request.method == "POST":
        req_form = await request.form
        if req_form['group'] and req_form['msg']:
            group = int(req_form['group'])
            message = req_form['msg']
            logger.debug(str(group), message)
            recipients, phone_nums = await Recipients.get_recipients(group)
            logger.debug(recipients)
            # TODO move messages to separate function
            # TODO log message to database
            for phone_num in phone_nums:
                twilio_msg = twilio.messages.create(to=phone_num,
                                                    from_=settings['twilio']['phone_num'],
                                                    body=message
                                                    )
                logger.info(f"{twilio_msg} sent to {', '.join(recipients)}")
            await flash(f"Message sent to: {', '.join(recipients)}")
        else:
            await flash("Error: All form fields are required.")
    return await render_template("sendmsg.html", form=form, choices=choices)  # , profile_pic=profile_pic)
    # else:
    #     return ("<h2>St. Petersburg Text App</h2>"
    #             "<a class='btn btn-default' href='/login' role='button'>Google Login</a>")

