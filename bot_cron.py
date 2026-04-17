import os
import time
import requests
import yfinance as yf
import google.generativeai as genai
from supabase import create_client

# 1. Recupero delle chiavi segrete da GitHub
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
TG_TOKEN = os.environ.get("TG_BOT_TOKEN") 

if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_KEY, TG_TOKEN]):
    print("❌ Errore: Mancano alcune chiavi segrete. Interruzione.")
    exit()

print("✅ Inizio procedura Morning Briefing...")

# 2. Estrazione dati super-veloce
tickers = ['^GSPC', 'BTC-USD', '^VIX']
# Usiamo threads=False per evitare fastidi con yfinance
data = yf.download(tickers, period="1d", progress=False, threads=False)['Close']
sp500 = data['^GSPC'].iloc[-1].item() if not data['^GSPC'].empty else 0
btc = data['BTC-USD'].iloc[-1].item() if not data['BTC-USD'].empty else 0
vix = data['^VIX'].iloc[-1].item() if not data['^VIX'].empty else 0

try:
    fgi_res = requests.get("https://api.alternative.me/fng/").json()
    fgi = fgi_res['data'][0]['value']
    fgi_class = fgi_res['data'][0]['value_classification']
except:
    fgi, fgi_class = "N/A", "N/A"

context = f"S&P 500: {sp500:.2f}, VIX: {vix:.2f}, Bitcoin: ${btc:.0f}, Fear & Greed Crypto: {fgi} ({fgi_class})."

# 3. Generazione Report con AI
print("🤖 Generazione report AI in corso...")
genai.configure(api_key=GEMINI_KEY)

# Puntiamo diretti al cavallo di battaglia gratuito, senza fare la ricerca dinamica
nome_modello = "gemini-1.5-flash"
print(f"Modello selezionato: {nome_modello}")

try:
    model = genai.GenerativeModel(nome_modello)
    prompt = f"Sei un CIO istituzionale. Scrivi un Morning Briefing per Telegram di MAX 150 parole basato su questi dati: {context}. Usa le emoji, sii professionale, incisivo e vai dritto al punto. Evita introduzioni inutili."
    report = model.generate_content(prompt).text
except Exception as e:
    print(f"❌ Errore durante la generazione AI: {e}")
    # Paracadute: se l'AI fallisce, mandiamo almeno i dati crudi
    report = f"📊 **Morning Briefing (Dati Raw)**\n\nS&P 500: {sp500:.2f}\nBitcoin: ${btc:.0f}\nVIX: {vix:.2f}\nFear&Greed: {fgi}"

# 4. Invio massivo su Telegram
print("📡 Connessione al database e invio messaggi...")
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    utenti = supabase.table("telegram_users").select("chat_id").execute()
    
    conteggio = 0
    for user in utenti.data:
        chat_id = user['chat_id']
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": report, "parse_mode": "Markdown"}
        res = requests.post(url, json=payload)
        
        if res.status_code == 200:
            conteggio += 1
        else:
            print(f"Errore invio a {chat_id}: {res.text}")
            
        # Pausa antispam di Telegram
        time.sleep(0.1)

    print(f"🎉 Finito! Messaggio inviato a {conteggio} utenti.")

except Exception as e:
    print(f"❌ Errore durante l'invio su Telegram: {e}")
