# Salvation Army Text App

This is a web app set up to facilitate texting small groups via Twilio.  It is written in 
Python using Quart and asyncpg.  Authentication is handled by Google.

Current issue: Flask-Login really doesn't like making async calls to my database to get 
the User object.

