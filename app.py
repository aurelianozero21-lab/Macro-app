import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser

st.set_page_config(page_title="Macro Dashboard v13.7", layout="wide")
st.title("📊 Global Macro, Crypto & Geopolitics")

with st.expander("📚 Legenda e Glossario"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo diviso per la media a 200 giorni. < 1.0 = Accumulo. > 2.4 = Bolla.
    * **RSI:** > 70 è ipercomprato (rischio calo), < 30 è ipervenduto (possibile rimbalzo).
    * **Rotazione Crypto:** Il flusso di capitali da Bitcoin -> Ethereum -> Altcoin -> Memecoin.
    """)

@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    assets = {
        'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F',
        'Petrolio': 'CL=F', 'Treasury 10Y': '^TNX'
    }
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="15y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
            
    btc_hist = yf.Ticker('BTC-USD').history(period="15y")
    btc_hist.index = pd.to_datetime(btc_hist.index).tz_localize(None).normalize()
    df['Bitcoin'] = btc_hist['Close']
    df['BTC_Volume'] = btc_hist['Volume']
    df['BTC_200DMA'] = df['Bitcoin'].rolling(window=200).mean()
    df['Mayer_BTC'] = df['Bitcoin'] / df['BTC_200DMA']
    df['BTC_Vol_30D'] = df['BTC_Volume'].rolling(window=30).mean()
    
    delta_btc = df['Bitcoin'].diff()
    rs_btc = (delta_btc.where(delta_btc > 0, 0)).rolling(window=14).mean() / (-delta_btc.where(delta_btc < 0, 0)).rolling(window=14).mean()
    df['RSI_BTC'] = 100 - (100 / (1 + rs_btc))

    eth_hist = yf.Ticker('ETH-USD').history(period="15y")
    eth_hist.index = pd.to_datetime(eth_hist.index).tz_localize(None).normalize()
    df['Ethereum'] = eth_hist['Close']
    df['ETH_200DMA'] = df['Ethereum'].rolling(window=200).mean()
    df['Mayer_ETH'] = df['Ethereum'] / df['ETH_200DMA']
    
    delta_eth = df['Ethereum'].diff()
    rs_eth = (delta_eth.where(delta_eth > 0, 0)).rolling(window=14).mean() / (-delta_eth.where(delta_eth < 0, 0)).rolling(window=14).mean()
    df['RSI_ETH'] = 100 - (100 / (1 + rs_eth))
    
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    df = df.ffill().dropna()
    
    for col in ['S&P 500', 'Dollaro DXY', 'Oro', 'Petrolio', 'Treasury 10Y', 'Bitcoin', 'Ethereum']:
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
    if not feed.entries: return 50, []
        
    risk_words = ['war', 'strike', 'tariff', 'sanction', 'crisis', 'escalat', 'missile', 'tension', 'conflict', 'invasion']
    peace_words = ['peace', 'deal', 'agreement', 'ceasefire', 'easing', 'stimulus', 'talks']
    
    risk_score_raw = 0
    news_items = []
    
    for entry in feed.entries[:25]:
        title = entry.title.lower()
        score = sum(1 for w in risk_words if w in title) - sum(1 for w in peace_words if w in title)
        risk_score_raw += score
        if score != 0 and len(news_items) < 8:
            news_items.append({'titolo': entry.title, 'link': entry.link, 'score': score})
            
    tension_index = max(0, min(100, 50 + (risk_score_raw * 4)))
    return tension_index, news_items

@st.cache_data(ttl=1800)
def get_crypto_news():
    url = "https://news.google.com/rss/search?q=bitcoin+OR+ethereum+OR+cryptocurrency+OR+blockchain&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    if not feed.entries: return []
    return [{'titolo': entry.title, 'link': entry.link} for entry in feed.entries[:8]]

lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

df, vix_val = pd.DataFrame(), 20
tension_index, top_news = 50, []
crypto_news = []

with st.spinner("📊 Scaricamento dati Macro..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        vix_val = get_vix()
    except Exception as e:
        st.error("Dati borsa non disponibili. Riprova più tardi.")
        st.stop()

with st.spinner("🌍 Analisi News Geopolitiche..."):
    try: tension_index, top_news = analyze_geopolitics()
    except: pass

with st.spinner("⚡ Scansione News Crypto..."):
    try: crypto_news = get_crypto_news()
    except: pass

if df.empty:
    st.error("Dati insufficienti. Ricarica la pagina.")
    st.stop()

current = df.iloc[-1]

tab1, tab2, tab3 = st.tabs(["🏛️ Macro & TradFi", "⚡ Crypto & News", "🌍 Geopolitica"])

with tab1:
    st.header("🚦 Semaforo Macro e Azionario")
    
    if current['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
        st.error("🚨 **FASE ATTUALE: RALLENTAMENTO / RECESSIONE**\n\n**Settori suggeriti:** Healthcare (XLV), Utilities (XLU)")
    elif current['Fase_Macro'] == '2. Ripresa (Accumulo)':
        st.warning("🔋 **FASE ATTUALE: RIPRESA ECONOMICA**\n\n**Settori suggeriti:** Tecnologia (XLK), Consumi (XLY)")
    else:
        st.success("🚀 **FASE ATTUALE: ESPANSIONE / RISK-ON**\n\n**Settori suggeriti:** Industriali (XLI), Finanziari (XLF)")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500", f"{current['Z_S&P 500']:.2f}")
    c2.metric("Dollaro DXY", f"{current['Z_Dollaro DXY']:.2f}")
    c3.metric("Oro", f"{current['Z_Oro']:.2f}")
    c4.metric("Treasury 10Y", f"{current['Z_Treasury 10Y']:.2f}")

with tab2:
    st.header("👑 Bitcoin (BTC) & Ecosistema")
    mayer_btc = current['Mayer_BTC']
    rsi_btc = current['RSI_BTC']
    
    # --- NUOVA SEZIONE: ROTAZIONE SETTORIALE CRYPTO ---
    if mayer_btc < 1.0:
        st.success("🔋 **Fase del Ciclo: Accumulo (Bear / Early Bull)**")
        st.markdown("🛡️ **Strategia Crypto:** Il mercato è spaventato o annoiato. La liquidità scarseggia. Le Altcoin in questa fase sanguinano contro Bitcoin.")
        st.markdown("🎯 **Cosa Sovrappesare:**\n* **Bitcoin (BTC) al 70-80%:** L'asset più sicuro per costruire il portafoglio base.\n* **Ethereum (ETH) al 20%:** Iniziare l'accumulo.\n* ❌ **Evitare le Memecoin e le micro-cap.**")
    elif mayer_btc < 2.0:
        st.warning("📈 **Fase del Ciclo: Bull Market (Mid Cycle)**")
        st.markdown("🌊 **Strategia Crypto:** Bitcoin ha già corso e la sua dominance inizia a scendere. I profitti di BTC ruotano verso i progetti con fondamentali solidi.")
        st.markdown("🎯 **Cosa Sovrappesare:**\n* **Ecosistema Ethereum (Layer 2 come Arbitrum, Optimism).**\n* **Layer 1 alternativi (Solana, Avalanche).**\n* **Protocolli DeFi storici (Aave, Uniswap).**")
    else:
        st.error("💥 **Fase del Ciclo: Bolla Speculativa (Euphoria)**")
        st.markdown("🎢 **Strategia Crypto:** Pura mania. Il barbiere ti chiede che crypto comprare. Rischio di crollo imminente altissimo.")
        st.markdown("🎯 **Cosa Sovrappesare:**\n* 💰 **Stablecoins (USDT, USDC):** Iniziare a vendere progressivamente BTC e Altcoin per mettere al sicuro i profitti in dollari digitali.\n* *In questa fase le Memecoin fanno i +1000%, ma è puramente azzardo.*")

    st.markdown("---")
    
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    col_b1.metric("Prezzo BTC", f"${current['Bitcoin']:,.0f}")
    col_b2.metric("Mayer Multiple", f"{mayer_btc:.2f}", delta="Bolla" if mayer_btc > 2.0 else "Accumulo" if mayer_btc < 1 else "Neutrale", delta_color="inverse" if mayer_btc > 2 else "normal")
    col_b3.metric("RSI (14 gg)", f"{rsi_btc:.0f}", delta="Ipercomprato" if rsi_btc > 70 else "Ipervenduto" if rsi_btc < 30 else "Normale", delta_color="inverse" if rsi_btc > 70 else "normal")
    col_b4.metric("Trend (Z-Score)", f"{current['Z_Bitcoin']:.2f}")

    st.markdown("---")
    st.header("💠 Ethereum (ETH)")
    mayer_eth = current['Mayer_ETH']
    rsi_eth = current['RSI_ETH']
    
    col_e1, col_e2, col_e3, col_e4 = st.columns(4)
    col_e1.metric("Prezzo ETH", f"${current['Ethereum']:,.0f}")
    col_e2.metric("Mayer Multiple", f"{mayer_eth:.2f}", delta="Bolla" if mayer_eth > 2.0 else "Sottocosto" if mayer_eth < 1 else "Normale", delta_color="inverse" if mayer_eth > 2 else "normal")
    col_e3.metric("RSI (14 gg)", f"{rsi_eth:.0f}", delta="Ipercomprato" if rsi_eth > 70 else "Ipervenduto" if rsi_eth < 30 else "Normale", delta_color="inverse" if rsi_eth > 70 else "normal")
    col_e4.metric("Trend (Z-Score)", f"{current['Z_Ethereum']:.2f}")

    st.markdown("---")
    st.header("📰 Crypto News Radar")
    if crypto_news:
        for item in crypto_news:
            st.markdown(f"- ⚡ [{item['titolo']}]({item['link']})")
    else:
        st.info("Feed notizie in aggiornamento.")

with tab3:
    st.header("🌍 Geopolitical News Scanner & Sector Rotation")
    col_g1, col_g2 = st.columns([1, 1])
    
    with col_g1:
        if tension_index < 40:
            st.success("🟢 **Stato: Distensione Globale**")
            st.markdown("🕊️ **Strategia:** Clima pacifico che favorisce il commercio internazionale e le supply chain globali.")
            st.markdown("🎯 **Settori da sovrappesare:**\n* **Mercati Emergenti (EEM)**\n* **Trasporti Globali (IYT)**\n* **Consumi Discrezionali (XLY)**")
        elif tension_index <= 60:
            st.warning("🟡 **Stato: Tensione Normale**")
            st.markdown("⚖️ **Strategia:** Normale rumore di fondo geopolitico. Nessun impatto drastico sui mercati atteso.")
            st.markdown("🎯 **Settori da sovrappesare:**\n* Segui le indicazioni primarie del *Semaforo Macro* nella Scheda 1.")
        else:
            st.error("🔴 **Stato: Allarme Geopolitico (Risk-Off)**")
            st.markdown("🛡️ **Strategia:** Rischio imminente di conflitti, sanzioni o rottura delle catene di approvvigionamento. Difendere il capitale.")
            st.markdown("🎯 **Settori da sovrappesare:**\n* **Difesa e Aerospazio (ITA)**\n* **Cybersecurity (CIBR)**\n* **Energia (XLE)**\n* **Oro (GLD)**")
        
    with col_g2:
        fig_geo = go.Figure(go.Indicator(
            mode="gauge+number", value=tension_index, title={'text': "Indice di Tensione"},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "black"},
                   'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"},
                             {'range': [60, 100], 'color': "#e57373"}],
                   'threshold': {'line': {'color': "red", 'width': 4}, 'value': tension_index}}))
        fig_geo.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_geo, use_container_width=True)
        
    st.subheader("📰 Ultime Notizie Analizzate")
    if top_news:
        for item in top_news:
            badge = "🔴 Tensione" if item['score'] > 0 else "🟢 Distensione" if item['score'] < 0 else "⚪ Neutrale"
            st.markdown(f"- **[{badge}]** [{item['titolo']}]({item['link']})")
    else:
        st.info("Nessuna notizia ad alta priorità rilevata.")
