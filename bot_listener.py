import telebot
import os
import threading
from flask import Flask
from supabase import create_client

# 1. SERVER FITTIZIO PER INGANNARE RENDER (Piano Gratuito)
app = Flask(__name__)
@app.route('/')
def home():
    return "Il Centralinista Telegram è sveglio e operativo! 🤖"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Avvia il server web in background
threading.Thread(target=run_server).start()

# 2. LOGICA DEL BOT TELEGRAM
bot = telebot.TeleBot(os.getenv("TG_BOT_TOKEN"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = str(message.chat.id)
    nome = message.from_user.first_name
    try:
        # Inserisce l'ID su Supabase
        supabase.table("telegram_users").insert({"chat_id": chat_id}).execute()
        bot.reply_to(message, f"Benvenuto {nome}! ✅\n\nSincronizzazione completata. Da domani mattina riceverai il Report Macro alle 07:30.")
        print(f"Nuovo iscritto: {nome}")
    except Exception as e:
        if "duplicate key" in str(e).lower() or "23505" in str(e):
            bot.reply_to(message, f"Bentornato {nome}! Il tuo ID è già nel nostro database. Sei pronto per ricevere i report.")
        else:
            bot.reply_to(message, "⚠️ Errore tecnico durante la registrazione. Riprova più tardi.")

print("Avvio ascolto Telegram...")
bot.polling(none_stop=True)
