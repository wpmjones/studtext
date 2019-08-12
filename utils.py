import requests
from config import settings
from db import Messages


def discord_log(msg):
    record = msg.record
    if record["exception"] or record['level'] in ("CRITICAL", "ERROR", "WARNING"):
        color = int.from_bytes([200, 0, 0], byteorder='big')
    elif record['level'] == "DEBUG":
        color = int.from_bytes([255, 255, 0], byteorder='big')
    else:
        color = int.from_bytes([0, 225, 0], byteorder='big')
    payload = {
        "embeds": [{
            "color": color,
            "title": f"{record['module']}:{record['function']}:{record['line']}",
            "fields": [{"name": record['level'], "value": record['message'], "inline": False}],
            "footer": {"text": record['time'].strftime("%Y-%m-%d %T.%f")}
        }]
    }
    requests.post(settings["discord"]["webhook"], json=payload)
    if record["exception"]:
        e_traceback = record["exception"].traceback
        send_text(settings["discord"]["webhook"], e_traceback)


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


def welcome_recipient(twilio, recipient_id, name, phone):
    body = (f"Welcome {name}! You've been added to a group for Salvation Army text messages. "
            f"If you have questions, talk to your corps officers. Text 'STOP' to cancel messages.")
    twilio_msg = twilio.messages.create(to=phone,
                                        from_=settings["twilio"]["phone_num"],
                                        body=body)
    Messages.add_message(twilio_msg.sid, "WELCOME", recipient_id, 0, body)


def welcome_user(twilio, user_id, name, phone):
    body = (f"Welcome {name}! You are now approved to send Salvation Army text messages. "
            f"Start now at https://satext.com.")
    twilio_msg = twilio.messages.create(to=phone,
                                        from_=settings["twilio"]["phone_num"],
                                        body=body)
    Messages.add_message(twilio_msg.sid, user_id, 0, 0, body)