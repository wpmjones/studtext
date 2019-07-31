from quart import Quart

app = Quart(__name__)


@app.route("/")
async def hello():
    return "<h1 style='color:blue'>Welcome to Salvation Army Texting</h1>"


if __name__ == "__main__":
    app.run(host="0.0.0.0")
