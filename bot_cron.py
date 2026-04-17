import os
import time
import requests
import feedparser
import yfinance as yf
import google.generativeai as genai
from supabase import create_client

# 1. Recupero delle chiavi segrete da GitHub
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
TG_TOKEN = os.environ.get("TG_BOT_TOKEN") 

if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_KEY, TG_TOKEN]):
    print("❌ Errore: Mancano chiavi segrete.")
    exit()

print("✅ Inizio procedura Morning Briefing...")

# 2. Estrazione dati di Mercato Completi (Aggiunti Oro e Petrolio)
tickers = ['^GSPC', 'BTC-USD', '^VIX', 'GC=F', 'CL=F']
data = yf.download(tickers, period="1d", progress=False, threads=False)['Close']

sp500 = data['^GSPC'].iloc[-1].item() if not data['^GSPC'].empty else 0
btc = data['BTC-USD'].iloc[-1].item() if not data['BTC-USD'].empty else 0
vix = data['^VIX'].iloc[-1].item() if not data['^VIX'].empty else 0
oro = data['GC=F'].iloc[-1].item() if not data['GC=F'].empty else 0
petrolio = data['CL=F'].iloc[-1].item() if not data['CL=F'].empty else 0

try:
    fgi_res = requests.get("https://api.alternative.me/fng/").json()
    fgi = fgi_res['data'][0]['value']
    fgi_class = fgi_res['data'][0]['value_classification']
except:
    fgi, fgi_class = "N/A", "N/A"

# 3. Estrazione Ultime Notizie Geopolitiche (Google News RSS)
print("📰 Lettura delle breaking news mondiali...")
try:
    # Cerca notizie su mercati, geopolitica e petrolio
    url_news = "https://news.google.com/rss/search?q=geopolitics+OR+oil+OR+stock+market&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url_news)
    top_news = [entry.title for entry in feed.entries[:3]]
    news_string = " | ".join(top_news)
except Exception as e:
    print(f"Errore RSS: {e}")
    news_string = "Nessuna notizia di rilievo."

# Il "Pasto" per l'Intelligenza Artificiale
context = f"""
DATI FINANZIARI:
S&P 500: {sp500:.2f}
VIX: {vix:.2f}
Bitcoin: ${btc:.0f}
Oro: ${oro:.2f}
Petrolio (WTI): ${petrolio:.2f}
Crypto Fear & Greed: {fgi} ({fgi_class})

ULTIME NOTIZIE GLOBALI (USALE PER CONTESTUALIZZARE I DATI):
{news_string}
"""

# 4. Generazione Report con AI
print("🤖 Generazione report AI in corso...")
genai.configure(api_key=GEMINI_KEY)
nome_modello = "gemini-1.5-flash"

try:
    model = genai.GenerativeModel(nome_modello)
    # IL NUOVO PROMPT: Diamo a Gemini la personalità della tua newsletter
    prompt = f"""Sei un Chief Investment Officer istituzionale. Scrivi il 'Morning Briefing' per un canale Telegram privato.
    Hai a disposizione i seguenti dati finanziari di chiusura e le breaking news di stamattina:
    {context}
    
    Il tuo obiettivo è scrivere un'analisi narrativa, unendo i puntini tra geopolitica e movimenti di mercato.
    Usa esattamente questa struttura a elenchi (massimo 200 parole in totale, sii conciso e asciutto, usa stile telegram):
    
    🌍 **GEOPOLITICA E MACRO:** (Riassumi l'impatto delle notizie odierne sulla stabilità globale in 2-3 righe).
    🛢️ **COMMODITIES (Oro & Petrolio):** (Analizza i prezzi di Oro e Petrolio alla luce delle tensioni/notizie).
    📈 **MERCATI & CRYPTO:** (Analizza S&P 500, VIX e Bitcoin, dicendo se c'è propensione o avversione al rischio).
    
    Non fare premesse o saluti. Inizia direttamente dal primo punto. Usa grassetti per evidenziare i concetti chiave."""
    
    report = model.generate_content(prompt).text
except Exception as e:
    print(f"❌ Errore AI: {e}")
    report = f"📊 **Morning Briefing Raw**\nS&P 500: {sp500:.2f}\nOro: ${oro:.2f}\nPetrolio: ${petrolio:.2f}\nBitcoin: ${btc:.0f}"

# 5. Invio massivo su Telegram
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
        if res.status_code == 200: conteggio += 1
        time.sleep(0.1)

    print(f"🎉 Finito! Messaggio inviato a {conteggio} utenti.")

except Exception as e:
    print(f"❌ Errore invio: {e}")
