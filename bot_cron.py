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
print("🤖 Generazione report AI in corso...")
genai.configure(api_key=GEMINI_KEY)

# --- RICERCA MODELLO INTELLIGENTE (ANTI-404 E ANTI-BLOCCO) ---
modelli_disponibili = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
# Cerchiamo un modello "flash" (veloce e gratuito) ma ESCLUDIAMO il 2.5 (sperimentale, con limite di 5)
modelli_sicuri = [m for m in modelli_disponibili if "flash" in m.lower() and "2.5" not in m.lower()]

# Prende il miglior modello sicuro disponibile sul tuo account
nome_modello = modelli_sicuri[0] if modelli_sicuri else modelli_disponibili[0]
print(f"Modello selezionato in automatico: {nome_modello}")

model = genai.GenerativeModel(nome_modello)

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
    # Aggiungiamo i filtri di sicurezza abbassati per permettere le news di geopolitica
    response = model.generate_content(
        prompt,
        safety_settings=[
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}
        ]
    )
    report = response.text
except Exception as e:
    print(f"❌ Errore AI: {e}")
    report = f"⚠️ Errore tecnico AI: {str(e)}"

# 6. Invio Telegram
print("📡 Connessione al database...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
utenti = supabase.table("telegram_users").select("chat_id").execute()

print(f"👥 Trovati {len(utenti.data)} utenti nel database.")

conteggio = 0
for user in utenti.data:
    chat_id = user['chat_id']
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    
    # TENTATIVO 1: Invio con formattazione elegante (Markdown)
    payload = {"chat_id": chat_id, "text": report, "parse_mode": "Markdown"}
    res = requests.post(url, json=payload)
    
    # TENTATIVO 2 (PIANO B): Se Telegram fa i capricci con gli asterischi, inviamo senza formattazione
    if res.status_code != 200 and "parse entities" in res.text:
        print(f"⚠️ Capriccio di formattazione per {chat_id}, attivo il Piano B...")
        payload_sicuro = {"chat_id": chat_id, "text": report}
        res = requests.post(url, json=payload_sicuro)
        
    if res.status_code == 200:
        print(f"✅ Messaggio consegnato a {chat_id}")
        conteggio += 1
    else:
        print(f"❌ Errore definitivo per {chat_id}: {res.text}")
        
    time.sleep(0.2)

print(f"🏁 Esecuzione terminata. Inviato a {conteggio} su {len(utenti.data)} utenti.")
