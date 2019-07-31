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
    # if current_user.is_authenticated:
    form = HomeForm(request.form)
    print(form.errors)
    # profile_pic = current_user.profile_pic
    if request.method == "POST":
        if form.validate():
            group = request.form['group']
            message = request.form['msg']
            # recipients, phone_nums = get_recipients(group)
            recipients = ["Patrick", "Jennifer"]
            phone_nums = ["+17274632720", "+17274631360"]
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
    return render_template("sendmsg.html", form=form)  # , profile_pic=profile_pic)
    # else:
    #     return ("<h2>St. Petersburg Text App</h2>"
    #             "<a class='btn btn-default' href='/login' role='button'>Google Login</a>")