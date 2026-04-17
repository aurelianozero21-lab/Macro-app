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

print("✅ Inizio procedura Morning Briefing [VERSIONE NARRATIVA 3.0]...")

# 2. Estrazione Dati con Calcolo Variazioni Percentuali
tickers = {
    'SP500': '^GSPC', 
    'BTC': 'BTC-USD', 
    'VIX': '^VIX', 
    'ORO': 'GC=F', 
    'PETROLIO': 'CL=F', 
    'EUROPA': '^STOXX50E', 
    'GIAPPONE': '^N225', 
    'CINA': '000001.SS'
}

# Scarichiamo 5 giorni per essere sicuri di avere le ultime due chiusure valide
data = yf.download(list(tickers.values()), period="5d", progress=False, threads=False)['Close'].ffill()

def get_stats(ticker_code):
    try:
        current_price = data[ticker_code].iloc[-1]
        prev_price = data[ticker_code].iloc[-2]
        pct_change = ((current_price - prev_price) / prev_price) * 100
        return current_price, pct_change
    except:
        return 0, 0

# Mappatura dei dati calcolati
stats = {name: get_stats(t) for name, t in tickers.items()}

try:
    fgi_res = requests.get("https://api.alternative.me/fng/").json()
    fgi = fgi_res['data'][0]['value']
    fgi_class = fgi_res['data'][0]['value_classification']
except:
    fgi, fgi_class = "N/A", "N/A"

# 3. Estrazione News
try:
    url_news = "https://news.google.com/rss/search?q=geopolitics+OR+oil+OR+china+OR+economy&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url_news)
    news_string = " | ".join([entry.title for entry in feed.entries[:3]])
except:
    news_string = "Nessuna notizia di rilievo."

# 4. Costruzione del contesto per l'AI
context = f"""
DATI DI MERCATO (Prezzo e Variazione %):
- S&P 500: {stats['SP500'][0]:.2f} ({stats['SP500'][1]:+.2f}%)
- Bitcoin: ${stats['BTC'][0]:.0f} ({stats['BTC'][1]:+.2f}%)
- Oro: ${stats['ORO'][0]:.2f} ({stats['ORO'][1]:+.2f}%)
- Petrolio WTI: ${stats['PETROLIO'][0]:.2f} ({stats['PETROLIO'][1]:+.2f}%)
- VIX: {stats['VIX'][0]:.2f}

SOLO VARIAZIONI PERCENTUALI (Per commento):
- Europa (Euro Stoxx): {stats['EUROPA'][1]:+.2f}%
- Giappone (Nikkei): {stats['GIAPPONE'][1]:+.2f}%
- Cina (Shanghai): {stats['CINA'][1]:+.2f}%

SENTIMENT: Crypto Fear & Greed {fgi} ({fgi_class})
NEWS: {news_string}
"""

# 5. Generazione Report Narrativo
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

prompt = f"""Sei un CIO istituzionale. Scrivi un Morning Briefing narrativo e incisivo (stile newsletter finanziaria).
Usa questi dati: {context}

REGOLE DI SCRITTURA:
1. NON fare elenchi puntati freddi. Scrivi paragrafi discorsivi.
2. Per S&P 500, Oro, Petrolio e BTC: cita SEMPRE sia il prezzo che la variazione %.
3. Per Europa e Asia (Cina/Giappone): cita SOLO la variazione percentuale nel discorso.
4. Struttura il messaggio in 4 sezioni con queste emoji:
   🌍 **MACRO & GEOPOLITICA**
   📈 **EQUITIES** (Commenta USA, Europa e Asia confrontandole)
   🛢️ **COMMODITIES**
   🪙 **DIGITAL ASSETS**

Sii professionale, telegrafico ma fluido. Massimo 200 parole."""

try:
    report = model.generate_content(prompt).text
except Exception as e:
    report = "⚠️ Errore generazione report AI."

# 6. Invio Telegram
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
utenti = supabase.table("telegram_users").select("chat_id").execute()

for user in utenti.data:
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                  json={"chat_id": user['chat_id'], "text": report, "parse_mode": "Markdown"})
    time.sleep(0.2)
