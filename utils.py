import requests
from loguru import logger
from config import settings
from db import Messages


def discord_log(msg):
    record = msg.record
    payload = {
        "embeds": [{
            "title": f"{record['module']}:{record['function']}:{record['line']}",
            "fields": [{"name": record['level'], "value": record['message'], "inline": False}],
            "footer": {"text": record['time'].strftime("%Y-%m-%d %T.%f")}
        }]
    }
    r = requests.post(settings["discord"]["webhook"], json=payload)
    if record["exception"]:
        content = f"python\n{record['exception']}"
        send_text(settings["discord"]["webhook"], content, block=1)


def send_text(webhook, text, block=None):
    """ Sends text ot channel, splitting if necessary """
    if len(text) < 1993:
        if block:
            payload = {"content": f"```{text}```"}
            requests.post(webhook, json=payload)
        else:
            payload = {"content": text}
            requests.post(webhook, json=payload)
    else:
        coll = ""
        for line in text.splitlines(keepends=True):
            if len(coll) + len(line) > 1993:
                # if collecting is going to be too long, send  what you have so far
                if block:
                    payload = {"content": f"```{coll}```"}
                    requests.post(webhook, json=payload)
                else:
                    payload = {"content": coll}
                    requests.post(webhook, json=payload)
                coll = ""
            coll += line
        if block:
            payload = {"content": f"```{coll}```"}
            requests.post(webhook, json=payload)
        else:
            payload = {"content": coll}
            requests.post(webhook, json=payload)


def welcome_message(twilio, recipient_id, name, phone):
    body = (f"Welcome {name}! You've been added to a group for Salvation Army text messages. "
            f"If you have questions, talk to your corps officers. Text 'STOP' to cancel messages.")
    twilio_msg = twilio.messages.create(to=phone,
                                        from_=settings["twilio"]["phone_num"],
                                        body=body)
    Messages.add_message(twilio_msg.sid, "WELCOME", recipient_id, 0, body)
