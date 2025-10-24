# wymagane: pip install websocket-client requests python-telegram-bot
import json
import time
import threading
from collections import deque, defaultdict
import requests
import websocket
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# --------- KONFIGURACJA (DOSTOSUJ) ----------
TELEGRAM_BOT_TOKEN = "7805151071:AAHrEMA0DTq5gB1No6IJBy1ORwTbwh3Ngy0"
# Możesz dodać wiele Chat ID — rozdziel przecinkami w nawiasie []
ALLOWED_CHAT_IDS = ["7684314138"]
BINANCE_WS = "wss://stream.binance.com:9443/ws/!miniTicker@arr"  # zbiorcze mini-tickery
WINDOW_SECONDS = 5
MIN_VOLUME_USD = 2000
PCT_THRESHOLD = 20.0
MIN_PRICE = 0.05
# --------------------------------------------

# prosty helper do wysyłki Telegram
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in ALLOWED_CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            r = requests.post(url, data=payload, timeout=10)
            if not r.ok:
                print(f"⚠️ Błąd wysyłki do {chat_id}: {r.text}")
        except Exception as e:
            print(f"Telegram send error ({chat_id}):", e)

# przechowujemy historię cen
price_history = defaultdict(lambda: deque())

# WS do Binance
def on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception as e:
        print("parse err", e)
        return

    ts = time.time()
    for entry in data:
        try:
            s = entry.get("s")
            price = float(entry.get("c", 0))
            if price <= 0:
                continue

            dq = price_history[s]
            dq.append((ts, price))
            while dq and dq[0][0] < ts - WINDOW_SECONDS - 5:
                dq.popleft()

            baseline = None
            for t0, p0 in dq:
                if t0 <= ts - WINDOW_SECONDS:
                    baseline = p0
            if baseline is None and dq:
                baseline = dq[0][1]
            if baseline is None:
                continue

            pct_change = (price - baseline) / baseline * 100.0
            if price >= MIN_PRICE and pct_change <= -PCT_THRESHOLD:
                symbol_name = s
                link = f"https://www.binance.com/en/trade/{symbol_name}"
                text = (f"🚨 <b>HUGE MOVE</b>\n"
                        f"Symbol: <b>{symbol_name}</b>\n"
                        f"Price: <b>{price:.8f}</b>\n"
                        f"Change ({WINDOW_SECONDS}s): <b>{pct_change:.1f}%</b>\n"
                        f"Link: {link}\n"
                        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))} UTC")
                print("ALERT:", text)
                send_telegram(text)
                dq.clear()
        except Exception as e:
            print("entry err", e)

def on_error(ws, error):
    print("WS error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WS closed", close_status_code, close_msg)

def on_open(ws):
    print("WS connected to Binance miniTicker stream")

def run_ws():
    while True:
        try:
            ws = websocket.WebSocketApp(BINANCE_WS,
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close,
                                        on_open=on_open)
            ws.run_forever()
        except Exception as e:
            print("WS loop exception:", e)
        time.sleep(5)

# ----------------- TELEGRAM BOT -----------------
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update

# sprawdza, czy użytkownik ma dostęp
def has_access(update: Update):
    return str(update.effective_chat.id) in ALLOWED_CHAT_IDS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update):
        await update.message.reply_text("❌ Nie masz dostępu do tego bota. Skontaktuj się z administratorem.")
        return
    await update.message.reply_text(
        "🤖 Bot działa! Będę wysyłał alerty o dużych skokach cenowych 🚀"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update):
        await update.message.reply_text("❌ Nie masz dostępu do tego bota. Skontaktuj się z administratorem.")
        return
    await update.message.reply_text(
        "📊 Bot uruchomiony i monitoruje rynek Binance."
    )

def run_telegram():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.run_polling()

# ----------------- MAIN -----------------
if __name__ == "__main__":
    print("Starting bot...")
    # wątki: jeden do Binance WS, drugi do Telegrama
    threading.Thread(target=run_ws, daemon=True).start()
    run_telegram()
