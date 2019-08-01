import quart.flask_patch

from db import User, Receipients
from quart import Quart, redirect, url_for, request, render_template, flash
from wtforms import Form, TextAreaField, SelectField, validators
from twilio.rest import Client
from config import settings

app = Quart(__name__)
app.config['SECRET_KEY'] = settings['flask']['key']

# Set up Twilio
twilio = Client(settings['twilio']['sid'], settings['twilio']['token'])


@app.route("/")
async def index():
    return redirect(url_for("sendmsg"))


class HomeForm(Form):
    group = SelectField("Recipients:")
    msg = TextAreaField("Message:", validators=[validators.required()])


@app.route("/sendmsg", methods=["GET", "POST"])
async def sendmsg():
    form = HomeForm()
    if request.method == "POST":
        form = HomeForm(await request.form)
        print(await form.validate())
        if await form.validate():
            group = await request.form['group']
            message = await request.form['msg']
            recipients, phone_nums = await Receipients.get_recipients(group)
            # recipients = ["Patrick", "Jennifer"]
            # phone_nums = ["+17274632720", "+17274631360"]
            # TODO move messages to separate function
            # TODO log message to database
            for phone_num in phone_nums:
                twilio_msg = twilio.messages.create(to=phone_num,
                                                    from_=settings['twilio']['phone_num'],
                                                    body=message
                                                    )
                print(twilio_msg)
            await flash(f"Message sent to: {', '.join(recipients)}")
        else:
            await flash("Error: All form fields are required.")
        # TODO figure out how to set up options in sendmgs.html from Receipients.columns()
    groups = await Receipients.get_groups()
    return await render_template("sendmsg.html", form=form, groups=groups)  # , profile_pic=profile_pic)
    # else:
    #     return ("<h2>St. Petersburg Text App</h2>"
    #             "<a class='btn btn-default' href='/login' role='button'>Google Login</a>")
