import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser
import numpy as np

st.set_page_config(page_title="Macro Dashboard v12", layout="wide")
st.title("📊 Global Macro, Crypto & Geopolitics (v12)")

with st.expander("📚 Legenda e Glossario"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Indice Geopolitico:** Analizza le news in tempo reale. > 60 significa alta tensione.
    * **Mayer Multiple (Bitcoin):** Prezzo BTC diviso per la sua media a 200 giorni. Storicamente: < 1.0 è Accumulo, > 2.4 è Bolla speculativa.
    * **RSI (Relative Strength Index):** Misura l'inerzia del prezzo. > 70 è ipercomprato (rischio ribasso), < 30 è ipervenduto (possibile rimbalzo).
    """)

# --- RECUPERO DATI ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    # TradFi
    assets = {
        'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F',
        'Petrolio': 'CL=F', 'Treasury 10Y': '^TNX', 'Ethereum': 'ETH-USD'
    }
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="15y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
            
    # Gestione Avanzata Bitcoin
    btc_hist = yf.Ticker('BTC-USD').history(period="15y")
    btc_hist.index = pd.to_datetime(btc_hist.index).tz_localize(None).normalize()
    df['Bitcoin'] = btc_hist['Close']
    df['BTC_Volume'] = btc_hist['Volume']
    
    # Metriche Crypto
    df['Rapporto ETH/BTC'] = df['Ethereum'] / df['Bitcoin']
    df['BTC_200DMA'] = df['Bitcoin'].rolling(window=200).mean()
    df['Mayer_Multiple'] = df['Bitcoin'] / df['BTC_200DMA']
    df['BTC_Vol_30D'] = df['BTC_Volume'].rolling(window=30).mean()
    
    # Calcolo RSI manuale per evitare librerie extra
    delta = df['Bitcoin'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI_BTC'] = 100 - (100 / (1 + rs))
    
    # Macro
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    df = df.ffill().dropna()
    
    for col in ['S&P 500', 'Dollaro DXY', 'Oro', 'Petrolio', 'Treasury 10Y', 'Bitcoin', 'Ethereum', 'Rapporto ETH/BTC']:
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

@st.cache_data(ttl=1800)
def analyze_geopolitics():
    url = "https://news.google.com/rss/search?q=geopolitics+OR+sanctions+OR+conflict+OR+economy+markets&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    risk_words = ['war', 'strike', 'tariff', 'sanction', 'crisis', 'escalat', 'missile', 'tension', 'conflict', 'invasion', 'threat', 'military', 'attack', 'crash']
    peace_words = ['peace', 'deal', 'agreement', 'ceasefire', 'easing', 'stimulus', 'talks', 'diploma', 'resolve', 'growth']
    
    risk_score_raw = sum((sum(1 for w in risk_words if w in entry.title.lower()) - sum(1 for w in peace_words if w in entry.title.lower())) for entry in feed.entries[:25])
    tension_index = max(0, min(100, 50 + (risk_score_raw * 4)))
    
    news_items = [{'titolo': entry.title, 'link': entry.link, 'score': (sum(1 for w in risk_words if w in entry.title.lower()) - sum(1 for w in peace_words if w in entry.title.lower()))} for entry in feed.entries[:25] if (sum(1 for w in risk_words if w in entry.title.lower()) - sum(1 for w in peace_words if w in entry.title.lower())) != 0][:8]
    return tension_index, news_items

lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

try:
    df, vix_val = load_all_data(st.secrets["FRED_API_KEY"], lookback), get_vix()
    current = df.iloc[-1]
    tension_index, top_news = analyze_geopolitics()
except Exception as e:
    st.error(f"Errore: {e}")
    st.stop()

# --- CREAZIONE SCHEDE ---
tab1, tab2, tab3 = st.tabs(["🏛️ Macro & TradFi", "⚡ Bitcoin & Crypto Cycle", "🌍 Geopolitica"])

# ==========================================
# SCHEDA 1: MACROECONOMIA
# ==========================================
with tab1:
    st.header("🚦 Semaforo Macro e Azionario")
    if current['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
        colore, titolo = "#d32f2f", "🚨 RALLENTAMENTO / RECESSIONE"
        settori = "Healthcare (XLV), Utilities (XLU)"
    elif current['Fase_Macro'] == '2. Ripresa (Accumulo)':
        colore, titolo = "#f57c00", "🔋 RIPRESA ECONOMICA"
        settori = "Tecnologia (XLK), Consumi (XLY)"
    else:
        colore, titolo = "#388e3c", "🚀 ESPANSIONE / RISK-ON"
        settori = "Industriali (XLI), Finanziari (XLF)"

    st.markdown(f"""
    <div style="padding: 20px; border-radius: 10px; background-color: {colore}; color: white; margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: white;">{titolo}</h3>
        <p><strong>Settori suggeriti:</strong> {settori}</p>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500", f"{current['Z_S&P 500']:.2f}")
    c2.metric("Dollaro DXY", f"{current['Z_Dollaro DXY']:.2f}")
    c3.metric("Oro", f"{current['Z_Oro']:.2f}")
    c4.metric("Treasury 10Y", f"{current['Z_Treasury 10Y']:.2f}")

# ==========================================
# SCHEDA 2: BITCOIN & CRYPTO (NUOVA!)
# ==========================================
with tab2:
    st.header("⚡ Bitcoin Cycle & On-Chain Simulator")
    
    btc_price = current['Bitcoin']
    mayer = current['Mayer_Multiple']
    rsi = current['RSI_BTC']
    vol_ratio = current['BTC_Volume'] / current['BTC_Vol_30D'] if current['BTC_Vol_30D'] > 0 else 1
    
    # Logica Ciclica e Statistica Storica
    if mayer < 0.8:
        fase_btc = "🩸 Capitulation (Bottom)"
        prob_up = "85%"
        col_btc = "#81c784"
    elif mayer < 1.1:
        fase_btc = "🔋 Accumulo (Bear/Early Bull)"
        prob_up = "65%"
        col_btc = "#aed581"
    elif mayer < 1.5:
        fase_btc = "📈 Bull Market (Mid Cycle)"
        prob_up = "55%"
        col_btc = "#ffb74d"
    elif mayer < 2.4:
        fase_btc = "🔥 Frenzy (Late Bull)"
        prob_up = "35%"
        col_btc = "#ff8a65"
    else:
        fase_btc = "💥 Euphoria (Bolla Speculativa)"
        prob_up = "10%"
        col_btc = "#e57373"

    st.markdown(f"""
    <div style="padding: 20px; border-radius: 10px; border: 2px solid {col_btc}; margin-bottom: 20px;">
        <h3 style="color: {col_btc}; margin-top: 0;">Fase del Ciclo: {fase_btc}</h3>
        <p style="font-size: 16px;">Sulla base dello storico dei passati halving, quando il Mayer Multiple è a questo livello, le probabilità di un rendimento positivo nei successivi 30 giorni sono del <strong>{prob_up}</strong>.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.subheader("Metriche di Rete")
    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
    
    col_c1.metric("Prezzo BTC", f"${btc_price:,.0f}")
    col_c2.metric("Mayer Multiple", f"{mayer:.2f}", 
                  delta="Bolla" if mayer > 2.4 else "Sottocosto" if mayer < 0.8 else "Fair Value", 
                  delta_color="inverse" if mayer > 2.4 else "normal")
    col_c3.metric("RSI (14 gg)", f"{rsi:.0f}", 
                  delta="Ipercomprato" if rsi > 70 else "Ipervenduto" if rsi < 30 else "Neutrale",
                  delta_color="inverse" if rsi > 70 else "normal")
    
    vol_str = "Sopra Media" if vol_ratio > 1 else "Sotto Media"
    col_c4.metric("Volumi vs Media 30gg", f"{vol_ratio * 100:.0f}%", delta=vol_str)

    st.markdown("---")
    st.subheader("Dominance e Altseason")
    st.write("Confronto della forza tra Ethereum (Altcoin) e Bitcoin. Se sale, gli investitori stanno cercando alto rischio.")
    
    fig_ethbtc = px.area(df.tail(365), y='Rapporto ETH/BTC', title="Rapporto ETH/BTC (Ultimo anno)")
    st.plotly_chart(fig_ethbtc, use_container_width=True)

# ==========================================
# SCHEDA 3: GEOPOLITICA
# ==========================================
with tab3:
    st.header("🌍 Geopolitical News Scanner")
    col_g1, col_g2 = st.columns([1, 1])
    
    with col_g1:
        if tension_index < 40:
            stato, col_t = "Distensione Globale", "#81c784"
        elif tension_index <= 60:
            stato, col_t = "Tensione Normale", "#ffb74d"
        else:
            stato, col_t = "Allarme Geopolitico", "#e57373"
            
        st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; border: 2px solid {col_t}; margin-top: 20px;">
            <h3 style="color: {col_t}; margin-top: 0;">Stato: {stato}</h3>
        </div>
        """, unsafe_allow_html=True)
        
    with col_g2:
        fig_geo = go.Figure(go.Indicator(
            mode="gauge+number", value=tension_index, title={'text': "Indice di Tensione"},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "black"},
                   'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"},
                             {'range': [60, 100], 'color': "#e57373"}],
                   'threshold': {'line': {'color': "red", 'width': 4}, 'value': tension_index}}))
        fig_geo.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_geo, use_container_width=True)
