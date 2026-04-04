import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser
import numpy as np

st.set_page_config(page_title="Macro Dashboard v13.1", layout="wide")
st.title("📊 Global Macro, Crypto & Geopolitics")

with st.expander("📚 Legenda e Glossario"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo diviso per la sua media a 200 giorni. < 1.0 = Sottocosto/Accumulo. > 2.4 = Bolla.
    * **RSI:** > 70 è ipercomprato (rischio calo), < 30 è ipervenduto (possibile rimbalzo).
    """)

# --- RECUPERO DATI MACRO E PREZZI ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    # TradFi
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
            
    # Gestione Avanzata Bitcoin
    btc_hist = yf.Ticker('BTC-USD').history(period="15y")
    btc_hist.index = pd.to_datetime(btc_hist.index).tz_localize(None).normalize()
    df['Bitcoin'] = btc_hist['Close']
    df['BTC_Volume'] = btc_hist['Volume']
    df['BTC_200DMA'] = df['Bitcoin'].rolling(window=200).mean()
    df['Mayer_BTC'] = df['Bitcoin'] / df['BTC_200DMA']
    df['BTC_Vol_30D'] = df['BTC_Volume'].rolling(window=30).mean()
    
    # Calcolo RSI BTC
    delta_btc = df['Bitcoin'].diff()
    rs_btc = (delta_btc.where(delta_btc > 0, 0)).rolling(window=14).mean() / (-delta_btc.where(delta_btc < 0, 0)).rolling(window=14).mean()
    df['RSI_BTC'] = 100 - (100 / (1 + rs_btc))

    # Gestione Avanzata Ethereum
    eth_hist = yf.Ticker('ETH-USD').history(period="15y")
    eth_hist.index = pd.to_datetime(eth_hist.index).tz_localize(None).normalize()
    df['Ethereum'] = eth_hist['Close']
    df['ETH_200DMA'] = df['Ethereum'].rolling(window=200).mean()
    df['Mayer_ETH'] = df['Ethereum'] / df['ETH_200DMA']
    
    # Calcolo RSI ETH
    delta
