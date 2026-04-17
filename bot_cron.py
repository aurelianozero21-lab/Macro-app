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

print("✅ Inizio procedura Morning Briefing [VERSIONE MASTER 4.0]...")

# 2. Estrazione Dati Globali (Inclusi Bond Treasury 10Y)
tickers = {
    'SP500': '^GSPC', 
    'BTC': 'BTC-USD', 
    'VIX': '^VIX', 
    'ORO': 'GC=F', 
    'PETROLIO': 'CL=F', 
    'EUROPA': '^STOXX50E', 
    'GIAPPONE': '^N225', 
    'CINA': '000001.SS',
    'BOND_10Y': '^TNX'  # Treasury Yield 10 Anni
}

# Scarichiamo 5 giorni per gestire i fusi orari e calcolare le variazioni
data = yf.download(list(tickers.values()), period="5d", progress=False, threads=False)['Close'].ffill()

def get_stats(ticker_code):
    try:
        current_price = data[ticker_code].iloc[-1]
        prev_price = data[ticker_code].iloc[-2]
        pct_change = ((current_price - prev_price) / prev_price) * 100
        return current_price, pct_change
    except:
        return 0, 0

# Calcolo statistiche per ogni asset
stats = {name: get_stats(t) for name, t in tickers.items()}

try:
    fgi_res = requests.get("https://api.alternative.me/fng/").json()
    fgi = fgi_res['data'][0]['value']
    fgi_class = fgi_res['data'][0]['value_classification']
except:
    fgi, fgi_class = "N/A", "N/A"

# 3. Estrazione News Geopolitiche e Macro
try:
    url_news = "https://news.google.com/rss/search?q=geopolitics+OR+fed+OR+economy+OR+markets&hl=en-US&gl=US&ceid=US:en"
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
- Treasury 10Y Yield: {stats['BOND_10Y'][0]:.2f}% ({stats['BOND_10Y'][1]:+.2f}%)
- VIX Index: {stats['VIX'][0]:.2f}

SOLO VARIAZIONI PERCENTUALI (Per analisi comparativa):
- Europa (Euro Stoxx): {stats['EUROPA'][1]:+.2f}%
- Giappone (Nikkei): {stats['GIAPPONE'][1]:+.2f}%
- Cina (Shanghai): {stats['CINA'][1]:+.2f}%

SENTIMENT: Crypto Fear & Greed {fgi} ({fgi_class})
NEWS RECENTI: {news_string}
"""

# 5. Generazione Report Narrativo Blindato
print("🤖 Generazione report AI in corso...")
genai.configure(api_key=GEMINI_KEY)

# Ricerca automatica modello 1.5 (Gratuito e stabile)
modelli_disponibili = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
modelli_sicuri = [m.name for m in modelli_disponibili if ("1.5" in m.name or "1.0" in m.name) and "vision" not in m.name]
nome_modello = modelli_sicuri[0] if modelli_sicuri else "models/gemini-1.5-flash"

model = genai.GenerativeModel(nome_modello)

prompt = f"""Sei un Chief Investment Officer. Scrivi un Morning Briefing narrativo (stile newsletter finanziaria).
Dati: {context}

REGOLE TASSATIVE:
1. INIZIA SEMPRE con il titolo: 🏛️ **GLOBAL MACRO BRIEFING** 🏛️
2. NON fare elenchi puntati. Scrivi paragrafi fluidi e professionali.
3. Per S&P 500, Oro, Petrolio, BTC e Treasury 10Y: cita SEMPRE prezzo e variazione %.
4. Per Europa e Asia: cita SOLO la variazione % nel discorso.
5. Struttura in 5 sezioni:
   🌍 **MACRO & GEOPOLITICA**
   📈 **EQUITIES** (Confronta USA, Europa e Asia)
   ⚖️ **BONDS & RATES** (Analizza il rendimento del Treasury 10Y e cosa implica per i mercati)
   🛢️ **COMMODITIES**
   🪙 **DIGITAL ASSETS**

Massimo 300 parole. Sii autorevole."""

try:
    response = model.generate_content(
        prompt,
        safety_settings=[{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_DANGEROUS_CONTENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_SEXUALLY_EXPLICIT"]]
    )
    report = response.text
except Exception as e:
    report = f"⚠️ Errore AI: {str(e)}"

# 6. Invio Telegram con "Piano B" per errori di formattazione
print("📡 Invio messaggi...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
utenti = supabase.table("telegram_users").select("chat_id").execute()

for user in utenti.data:
    chat_id = user['chat_id']
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    
    # Tentativo A (Elegante)
    res = requests.post(url, json={"chat_id": chat_id, "text": report, "parse_mode": "Markdown"})
    
    # Tentativo B (Sicuro - se il Markdown fallisce)
    if res.status_code != 200:
        requests.post(url, json={"chat_id": chat_id, "text": report})
    
    time.sleep(0.2)

print(f"🏁 Finito! Report inviato a {len(utenti.data)} utenti.")
