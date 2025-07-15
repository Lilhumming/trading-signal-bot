import logging
from flask import Flask, request
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd
import requests
import datetime
import ta

# --- CONFIGURATION ---
BOT_TOKEN = "7153690037:AAFojBFFqqUA5z2GQ63tm6P290ta070LiLo"
CHAT_ID = "7147175084"
ASSET = "EURUSD"
INTERVAL = "1m"
DATA_LIMIT = 100
SILENT_DAY = "Sunday"

# --- LOGGER ---
logging.basicConfig(level=logging.INFO)

# --- TELEGRAM SETUP ---
bot = Bot(token=BOT_TOKEN)
app = ApplicationBuilder().token(BOT_TOKEN).build()

# --- CSV LOGGING ---
def log_signal(signal, rsi, macd):
    df = pd.DataFrame([{
        "timestamp": datetime.datetime.now(),
        "signal": signal,
        "rsi": rsi,
        "macd": macd
    }])
    df.to_csv("signal_log.csv", mode="a", header=False, index=False)

# --- SIGNAL ENGINE ---
def fetch_data():
    url = f"https://api.binance.com/api/v3/klines?symbol={ASSET}T&interval={INTERVAL}&limit={DATA_LIMIT}"
    res = requests.get(url)
    data = res.json()
    df = pd.DataFrame(data, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
    ])
    df["close"] = pd.to_numeric(df["close"])
    return df

def generate_signal():
    if datetime.datetime.now().strftime("%A") == SILENT_DAY:
        return

    df = fetch_data()
    close = df["close"]

    df["rsi"] = ta.momentum.RSIIndicator(close).rsi()
    df["macd"] = ta.trend.MACD(close).macd_diff()

    latest_rsi = df["rsi"].iloc[-1]
    latest_macd = df["macd"].iloc[-1]

    if latest_rsi < 30 and latest_macd > 0:
        signal = "BUY 🔼"
    elif latest_rsi > 70 and latest_macd < 0:
        signal = "SELL 🔽"
    else:
        signal = "HOLD ⏸"

    message = f"📊 Signal: {signal}\nRSI: {latest_rsi:.2f}\nMACD: {latest_macd:.5f}"
    bot.send_message(chat_id=CHAT_ID, text=message)
    log_signal(signal, latest_rsi, latest_macd)

# --- TELEGRAM COMMANDS ---
async def start(update, context):
    await update.message.reply_text("🤖 Hello! I will send trading signals every 10 mins.")

app.add_handler(CommandHandler("start", start))

# --- SCHEDULER ---
scheduler = BackgroundScheduler()
scheduler.add_job(generate_signal, "interval", minutes=10)
scheduler.start()

# --- FLASK FOR RENDER KEEP-ALIVE ---
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running."

@flask_app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    app.update_queue.put(request.json)
    return "ok"

# --- RUN BOT ---
if __name__ == "__main__":
    import threading

    def run_bot():
        app.run_polling()

    def run_flask():
        flask_app.run(host="0.0.0.0", port=8080)

    threading.Thread(target=run_bot).start()
    threading.Thread(target=run_flask).start()
