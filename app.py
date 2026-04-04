import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser

st.set_page_config(page_title="Macro Dashboard v13.4", layout="wide")
st.title("📊 Global Macro, Crypto & Geopolitics")

with st.expander("📚 Legenda e Glossario"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo diviso per la media a 200 giorni. < 1.0 = Accumulo. > 2.4 = Bolla.
    * **RSI:** > 70 è ipercomprato (rischio calo), < 30 è ipervenduto (possibile rimbalzo).
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
        if row['YieldCurve'] < 0: 
            return '1. Allarme Rosso (Recessione)'
        elif row['YieldCurve'] > 0 and row['Z_S&P 500'] < 0: 
            return '2. Ripresa (Accumulo)'
        else: 
            return '3. Espansione (Risk-On)'
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
    if not feed.entries: 
        return 50, []
        
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
    if not feed.entries: 
        return []
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
    try: 
        tension_index, top_news = analyze_geopolitics()
    except Exception: 
        pass

with st.spinner("⚡ Scansione News Crypto..."):
    try: 
        crypto_news = get_crypto_news()
    except Exception: 
        pass

if df.empty:
    st.error("Dati insufficienti. Ricarica la pagina.")
    st.stop()

current = df.iloc[-1]

tab1, tab2, tab3 = st.tabs(["🏛️ Macro & TradFi", "⚡ Crypto & News"]),
