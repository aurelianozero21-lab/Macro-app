import os
import time
import requests
import feedparser
import yfinance as yf
import google.generativeai as genai
from supabase import create_client

# 1. Recupero delle chiavi segrete
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
TG_TOKEN = os.environ.get("TG_BOT_TOKEN") 

if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_KEY, TG_TOKEN]):
    print("❌ Errore: Mancano chiavi segrete.")
    exit()

print("🚀🚀🚀 STO LEGGENDO IL FILE NUOVO 🚀🚀🚀")

# 2. Estrazione Dati Globali (Inclusa la Cina: 000001.SS)
tickers = ['^GSPC', 'BTC-USD', '^VIX', 'GC=F', 'CL=F', '^STOXX50E', '^N225', '000001.SS']
# Scarichiamo 5 giorni e "riempiamo i buchi" (ffill) per fusi orari disallineati
data = yf.download(tickers, period="5d", progress=False, threads=False)['Close'].ffill()

sp500 = data['^GSPC'].iloc[-1].item() if not data['^GSPC'].empty else 0
vix = data['^VIX'].iloc[-1].item() if not data['^VIX'].empty else 0
btc = data['BTC-USD'].iloc[-1].item() if not data['BTC-USD'].empty else 0
oro = data['GC=F'].iloc[-1].item() if not data['GC=F'].empty else 0
petrolio = data['CL=F'].iloc[-1].item() if not data['CL=F'].empty else 0
europa = data['^STOXX50E'].iloc[-1].item() if not data['^STOXX50E'].empty else 0
giappone = data['^N225'].iloc[-1].item() if not data['^N225'].empty else 0
cina = data['000001.SS'].iloc[-1].item() if not data['000001.SS'].empty else 0

try:
    fgi_res = requests.get("https://api.alternative.me/fng/").json()
    fgi = fgi_res['data'][0]['value']
    fgi_class = fgi_res['data'][0]['value_classification']
except:
    fgi, fgi_class = "N/A", "N/A"

# 3. Estrazione Ultime Notizie Geopolitiche (Con focus su Cina)
print("📰 Lettura delle breaking news mondiali...")
try:
    url_news = "https://news.google.com/rss/search?q=geopolitics+OR+oil+OR+stock+market+OR+europe+OR+china&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url_news)
    top_news = [entry.title for entry in feed.entries[:3]]
    news_string = " | ".join(top_news)
except Exception as e:
    print(f"Errore RSS: {e}")
    news_string = "Nessuna notizia di rilievo."

# Il "Pasto" completo per l'AI
context = f"""
DATI FINANZIARI DI CHIUSURA:
- USA (S&P 500): {sp500:.2f}
- Europa (Euro Stoxx 50): {europa:.2f}
- Giappone (Nikkei 225): {giappone:.2f}
- Cina (Shanghai Composite): {cina:.2f}
- Indice della Paura (VIX): {vix:.2f}
- Oro: ${oro:.2f}
- Petrolio (WTI): ${petrolio:.2f}
- Bitcoin: ${btc:.0f}
- Crypto Fear & Greed: {fgi} ({fgi_class})

ULTIME NOTIZIE GLOBALI:
{news_string}
"""

# 4. Generazione Report con AI
print("🤖 Generazione report AI in corso...")
genai.configure(api_key=GEMINI_KEY)
nome_modello = "gemini-1.5-flash"

try:
    model = genai.GenerativeModel(nome_modello)
    prompt = f"""Sei un Chief Investment Officer istituzionale. Scrivi il 'Morning Briefing' per un canale Telegram.
    Usa questi dati appena aggiornati:
    {context}
    
    DEVI obbligatoriamente usare questa struttura esatta e questi titoli per i tuoi paragrafi. Sii incisivo, usa tono istituzionale, non fare premesse, massimo 250 parole:
    
    🌍 **MACRO & GEOPOLITICA:** (Unisci le notizie odierne e il sentiment globale).
    📉 **AZIONARIO GLOBALE (USA, EU, ASIA):** (Commenta le chiusure di S&P500, Europa, e metti a confronto la situazione tra Giappone e Cina. Cita il livello del VIX).
    🛢️ **COMMODITIES:** (Analizza le mosse di Oro e Petrolio rispetto alle tensioni o alla domanda cinese).
    🪙 **ASSET DIGITALI:** (Analizza Bitcoin e l'indice Fear & Greed).
    
    Concludi con una singola riga di Outlook strategico."""
    
    report = model.generate_content(prompt).text
except Exception as e:
    print(f"❌ Errore AI: {e}")
    report = f"📊 **Morning Briefing Raw**\nS&P500: {sp500:.2f}\nEuropa: {europa:.2f}\nCina: {cina:.2f}\nOro: ${oro:.2f}\nPetrolio: ${petrolio:.2f}\nBTC: ${btc:.0f}"

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
