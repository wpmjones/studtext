import json
from flask import Flask, render_template, flash, request
from wtforms import Form, TextAreaField, SelectField, validators
from twilio.rest import Client
from config import settings

app = Flask(__name__)
app.config.from_object(__name__)
app.config["SECRET_KEY"] = "7d441f27d441f27567d441f2b6176a"

sid = settings['twilio']['sid']
token = settings['twilio']['token']
twilio = Client(sid, token)

choices = [("staff", "Staff"),
           ("students", "Students"),
           ("band", "Band"),
           ("songsters", "Songsters"),
           ("tester", "Debug")
           ]


def get_recipients(group):
    recipients = ""
    phone_nums = []
    with open("data/contacts.json") as f:
        contacts = json.load(f)
        for person in contacts:
            if person[group]:
                recipients += f"{person['name']}, "
                phone_nums.append(person['phone'])
    return recipients[:-2], phone_nums


class HomeForm(Form):
    group = SelectField("Receipients:", choices=choices)
    msg = TextAreaField("Message:", validators=[validators.required()])

    @app.route("/", methods=["GET", "POST"])
    def home():
        form = HomeForm(request.form)
        print(form.errors)
        if request.method == "POST":
            if form.validate():
                group = request.form['group']
                message = request.form['msg']
                recipients, phone_nums = get_recipients(group)
                for phone_num in phone_nums:
                    twilio_msg = twilio.messages.create(to=phone_num,
                                                        from_=settings['twilio']['phone_num'],
                                                        body=message
                                                        )
                    print(twilio_msg)
                flash(f"To: {recipients}")
                flash(message)
            else:
                flash("Error: All form fields are required.")
        return render_template("index.html", form=form)

    @app.route("/contacts")
    def contacts():
        return render_template("contacts.html")


if __name__ == "__main__":
    app.run(debug=True)
