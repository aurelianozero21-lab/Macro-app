import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser

st.set_page_config(page_title="Macro Dashboard v11", layout="wide")
st.title("📊 Global Macro, Crypto & Geopolitics (v11)")

with st.expander("📚 Legenda e Glossario"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Indice Geopolitico:** Analizza le news in tempo reale. > 70 significa alta tensione (Risk-Off globale).
    """)

# --- RECUPERO DATI MACRO E CRYPTO ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    assets = {
        'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F',
        'Petrolio': 'CL=F', 'Treasury 10Y': '^TNX', 'Bitcoin': 'BTC-USD', 'Ethereum': 'ETH-USD'
    }
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="15y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
            
    df['Rapporto ETH/BTC'] = df['Ethereum'] / df['Bitcoin']
    
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    df = df.ffill().dropna()
    
    for col in df.columns:
        if col != 'YieldCurve':
            df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    df = df.dropna()
    def assegna_fase(row):
        if row['YieldCurve'] < 0: return '1. Allarme Rosso (Recessione)'
        elif row['YieldCurve'] > 0 and row['Z_S&P 500'] < 0: return '2. Ripresa (Accumulo)'
        else: return '3. Espansione (Risk-On)'
    df['Fase_Macro'] = df.apply(assegna_fase, axis=1)
    return df

@st.cache_data(ttl=900)
def get_vix():
    vix = yf.Ticker('^VIX').history(period="1mo")['Close']
    return vix.iloc[-1] if not vix.empty else 20

# --- MOTORE NLP PER NEWS GEOPOLITICHE ---
@st.cache_data(ttl=1800) # Aggiorna ogni 30 minuti
def analyze_geopolitics():
    # Legge le news globali da Google News in inglese
    url = "https://news.google.com/rss/search?q=geopolitics+OR+sanctions+OR+conflict+OR+economy+markets&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    
    # Dizionari di sentiment (in inglese, lingua madre della finanza)
    risk_words = ['war', 'strike', 'tariff', 'sanction', 'crisis', 'escalat', 'missile', 'tension', 'conflict', 'invasion', 'threat', 'military', 'attack', 'crash']
    peace_words = ['peace', 'deal', 'agreement', 'ceasefire', 'easing', 'stimulus', 'talks', 'diploma', 'resolve', 'growth']
    
    risk_score_raw = 0
    news_items = []
    
    for entry in feed.entries[:25]:
        title = entry.title.lower()
        r_count = sum(1 for w in risk_words if w in title)
        p_count = sum(1 for w in peace_words if w in title)
        
        net_score = r_count - p_count
        risk_score_raw += net_score
        
        # Salviamo la news solo se ha una rilevanza (score != 0) o è tra le primissime
        if net_score != 0 or len(news_items) < 5:
            news_items.append({'titolo': entry.title, 'link': entry.link, 'score': net_score})
            
    # Normalizziamo il punteggio su una scala 0-100 (50 è neutrale)
    tension_index = 50 + (risk_score_raw * 4)
    tension_index = max(0, min(100, tension_index))
    
    return tension_index, news_items[:8] # Restituiamo le top 8 news

lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

try:
    df, vix_val = load_all_data(st.secrets["FRED_API_KEY"], lookback), get_vix()
    current = df.iloc[-1]
    tension_index, top_news = analyze_geopolitics()
except Exception as e:
    st.error(f"Errore dati: Assicurati di aver inserito 'feedparser' nel file requirements.txt e riavviato l'app! Dettaglio: {e}")
    st.stop()

# --- CREAZIONE DELLE 3 SCHEDE ---
tab1, tab2, tab3 = st.tabs(["🏛️ Macro & TradFi", "⚡ Crypto", "🌍 Geopolitica & Sentiment"])

# ==========================================
# SCHEDA 1: MACROECONOMIA
# ==========================================
with tab1:
    st.header("🚦 Semaforo Macro")
    if current['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
        colore, titolo = "#d32f2f", "🚨 RALLENTAMENTO / RECESSIONE"
    elif current['Fase_Macro'] == '2. Ripresa (Accumulo)':
        colore, titolo = "#f57c00", "🔋 RIPRESA ECONOMICA"
    else:
        colore, titolo = "#388e3c", "🚀 ESPANSIONE / RISK-ON"

    st.markdown(f"""
    <div style="padding: 20px; border-radius: 10px; background-color: {colore}; color: white; margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: white;">{titolo}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500", f"{current['Z_S&P 500']:.2f}")
    c2.metric("Dollaro DXY", f"{current['Z_Dollaro DXY']:.2f}")
    c3.metric("Oro", f"{current['Z_Oro']:.2f}")
    c4.metric("Treasury 10Y", f"{current['Z_Treasury 10Y']:.2f}")

# ==========================================
# SCHEDA 2: CRYPTO
# ==========================================
with tab2:
    st.header("⚡ Ecosistema Crypto")
    c1, c2, c3 = st.columns(3)
    c1.metric("Z-Score Bitcoin", f"{current['Z_Bitcoin']:.2f}")
    c2.metric("Z-Score Ethereum", f"{current['Z_Ethereum']:.2f}")
    c3.metric("Rischio Crypto (ETH/BTC)", f"{current['Z_Rapporto ETH/BTC']:.2f}")

# ==========================================
# SCHEDA 3: GEOPOLITICA E NEWS (NUOVA!)
# ==========================================
with tab3:
    st.header("🌍 Geopolitical News Scanner")
    st.write("L'algoritmo legge i feed delle testate globali in tempo reale e analizza il linguaggio per determinare il livello di tensione internazionale.")
    
    col_g1, col_g2 = st.columns([1, 1])
    
    with col_g1:
        if tension_index < 40:
            stato = "Distensione Globale"
            col_t = "#81c784"
            sug_geo = "Ottimo ambiente per **Azioni Globali (VT)** e **Mercati Emergenti (EEM)**. Il commercio fluisce, le catene di approvvigionamento sono intatte."
        elif tension_index <= 60:
            stato = "Tensione Normale"
            col_t = "#ffb74d"
            sug_geo = "Fisiologici rumori di fondo geopolitici. Mantieni l'allocazione dettata dalla Scheda Macro."
        else:
            stato = "Allarme Geopolitico (Risk-Off)"
            col_t = "#e57373"
            sug_geo = "Forti venti di crisi! Valuta coperture: **Settore Difesa/Armi (ITA)**, **Cybersecurity (CIBR)**, **Oro (GLD)** e **Dollaro USA (UUP)**. Evita mercati emergenti esposti."
            
        st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; border: 2px solid {col_t}; margin-top: 20px;">
            <h3 style="color: {col_t}; margin-top: 0;">Stato: {stato}</h3>
            <p><strong>Cosa comprare/fare:</strong> {sug_geo}</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col_g2:
        fig_geo = go.Figure(go.Indicator(
            mode="gauge+number", value=tension_index, title={'text': "Indice di Tensione Geopolitica"},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "black"},
                   'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"},
                             {'range': [60, 100], 'color': "#e57373"}],
                   'threshold': {'line': {'color': "red", 'width': 4}, 'value': tension_index}}))
        fig_geo.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_geo, use_container_width=True)

    st.markdown("---")
    st.subheader("📰 Ultime Notizie Analizzate dall'Algoritmo")
    st.write("Le notizie lette e i punti assegnati (Valori positivi = Tensione, Valori negativi = Pace/Accordi).")
    
    for item in top_news:
        if item['score'] > 0:
            badge = "🔴 Tensione"
        elif item['score'] < 0:
            badge = "🟢 Distensione"
        else:
            badge = "⚪ Neutrale"
            
        st.markdown(f"- **[{badge}]** [{item['titolo']}]({item['link']})")
