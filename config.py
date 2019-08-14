import yaml
from twilio.rest import Client

with open("config.yaml", "r") as f:
    settings = yaml.load(f, Loader=yaml.Loader)

twilio = Client(settings["twilio"]["sid"], settings["twilio"]["token"])
