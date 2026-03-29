from flask import Flask
import threading
import subprocess

app = Flask(__name__)

@app.route("/")
def home():
    return "bot is running"

def run_bot():
    subprocess.Popen(["python", "bot.py"])

threading.Thread(target=run_bot).start()

app.run(host="0.0.0.0", port=8080)
