from quart import Quart

app = Quart(__name__)


@app.route("/")
async def hello():
    return "<h1 style='color:blue'>Welcome to Salvation Army Texting!</h1>"
