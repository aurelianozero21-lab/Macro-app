import yfinance as yf
import pandas as pd
from fredapi import Fred
import feedparser
import urllib.request
import json
import streamlit as st

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

def init_supabase():
    if SUPABASE_AVAILABLE and "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    return None

@st.cache_data(ttl=60)
def get_live_prices():
    tickers = ['^GSPC', 'BTC-USD', 'GC=F', '^VIX', 'CL=F']
    prices = {}
    for t in tickers:
        try:
            data = yf.download(t, period="1d", interval="2m", progress=False)
            prices[t] = data['Close'].iloc[-1].item() if not data.empty else 0
        except:
            prices[t] = 0
    return prices

@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    # Aggiunto 'Bond ETF' (IEF) per backtest reale obbligazionario
    assets = {'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F', 'Treasury 10Y': '^TNX', 'High Yield': 'HYG', 'VIX': '^VIX', 'Bond ETF': 'IEF'}
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="15y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
            
    btc_hist = yf.Ticker('BTC-USD').history(period="15y")
    btc_hist.index = pd.to_datetime(btc_hist.index).tz_localize(None).normalize()
    df['Bitcoin'] = btc_hist['Close']
    df['BTC_ATH'] = df['Bitcoin'].cummax()
    df['BTC_Drawdown'] = ((df['Bitcoin'] - df['BTC_ATH']) / df['BTC_ATH']) * 100
    df['BTC_200DMA'] = df['Bitcoin'].rolling(window=200).mean()
    df['Mayer_BTC'] = df['Bitcoin'] / df['BTC_200DMA']
    
    delta_btc = df['Bitcoin'].diff()
    rs_btc = (delta_btc.where(delta_btc > 0, 0)).rolling(window=14).mean() / (-delta_btc.where(delta_btc < 0, 0)).rolling(window=14).mean()
    df['RSI_BTC'] = 100 - (100 / (1 + rs_btc))
    
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    
    df['WALCL'] = fred.get_series('WALCL')
    df['WTREGEN'] = fred.get_series('WTREGEN')
    df['RRPONTSYD'] = fred.get_series('RRPONTSYD')
    
    df = df.ffill().dropna()
    
    df['Fed_Liquidity_T'] = (df['WALCL'] / 1000000) - (df['WTREGEN'] / 1000000) - (df['RRPONTSYD'] / 1000)
    df['Liquidity_Delta_30d'] = df['Fed_Liquidity_T'].diff(periods=21)
    
    for col in ['S&P 500', 'Dollaro DXY', 'Oro', 'Treasury 10Y', 'Bitcoin', 'High Yield', 'VIX', 'Fed_Liquidity_T']:
        df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    return df.dropna()

def calcola_backtest(df, pesi):
    colonne = ['S&P 500', 'Bond ETF', 'Bitcoin', 'Oro']
    df_bt = df[colonne].copy()
    rendimenti = df_bt.pct_change().dropna()
    
    rendimenti['Portafoglio'] = (
        rendimenti['S&P 500'] * pesi['Azioni'] +
        rendimenti['Bond ETF'] * pesi['Bonds'] +
        rendimenti['Bitcoin'] * pesi['Crypto'] +
        rendimenti['Oro'] * pesi['Difesa']
    )
    
    capitale_iniziale = 10000
    equity = (1 + rendimenti['Portafoglio']).cumprod() * capitale_iniziale
    equity_sp500 = (1 + rendimenti['S&P 500']).cumprod() * capitale_iniziale
    
    anni = len(rendimenti) / 252
    cagr = (equity.iloc[-1] / capitale_iniziale) ** (1 / anni) - 1 if anni > 0 else 0
    max_dd = ((equity - equity.cummax()) / equity.cummax()).min()
    
    return equity, equity_sp500, cagr, max_dd

@st.cache_data(ttl=3600)
def get_etf_screener():
    tickers = {'USA (SPY)': 'SPY', 'Europa (VGK)': 'VGK', 'Emergenti (EEM)': 'EEM', 'Giappone (EWJ)': 'EWJ', 'Tech (XLK)': 'XLK', 'Salute (XLV)': 'XLV', 'Finanza (XLF)': 'XLF', 'Energia (XLE)': 'XLE', 'Utilities (XLU)': 'XLU', 'Industria (XLI)': 'XLI'}
    dati = []
    for nome, tk in tickers.items():
        try:
            hist = yf.Ticker(tk).history(period="1y")
            if len(hist) > 50:
                prezzo, sma_50, sma_200 = hist['Close'].iloc[-1], hist['Close'].tail(50).mean(), hist['Close'].mean() 
                perf_1m = ((prezzo / hist['Close'].iloc[-21]) - 1) * 100
                segnale = "🟢 Compra" if prezzo > sma_50 and sma_50 > sma_200 else "🟡 Accumula" if prezzo > sma_50 else "🔴 Evita"
                tipo = 'Geografia' if nome in ['USA (SPY)', 'Europa (VGK)', 'Emergenti (EEM)', 'Giappone (EWJ)'] else 'Settore'
                dati.append({'Categoria': tipo, 'Asset': nome, 'Prezzo ($)': round(prezzo, 2), 'Perf. 1 Mese (%)': round(perf_1m, 2), 'Segnale Operativo': segnale})
        except: continue
    return pd.DataFrame(dati)

@st.cache_data(ttl=3600)
def get_crypto_screener():
    tickers = {'Bitcoin': 'BTC-USD', 'Ethereum': 'ETH-USD', 'Solana': 'SOL-USD', 'Binance': 'BNB-USD', 'Avalanche': 'AVAX-USD'}
    dati = []
    for nome, tk in tickers.items():
        try:
            hist = yf.Ticker(tk).history(period="1y")
            if len(hist) > 50:
                prezzo, sma_50, sma_200 = hist['Close'].iloc[-1], hist['Close'].tail(50).mean(), hist['Close'].mean() 
                perf_1m = ((prezzo / hist['Close'].iloc[-21]) - 1) * 100
                dati.append({'Asset': nome, 'Prezzo ($)': round(prezzo, 2), 'Perf. 1 Mese (%)': round(perf_1m, 2)})
        except: continue
    return pd.DataFrame(dati)

@st.cache_data(ttl=1800)
def get_crypto_fgi():
    try:
        with urllib.request.urlopen("https://api.alternative.me/fng/") as url:
            data = json.loads(url.read().decode())
            return int(data['data'][0]['value']), data['data'][0]['value_classification']
    except: return 50, "Neutral"

@st.cache_data(ttl=1800)
def analyze_geopolitics():
    url = "https://news.google.com/rss/search?q=geopolitics+OR+sanctions+OR+conflict+OR+economy+markets&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    if not feed.entries: return 50, [], {}
    risk_words, peace_words = ['war', 'strike', 'tariff', 'sanction', 'missile', 'tension', 'conflict'], ['peace', 'deal', 'agreement', 'ceasefire', 'talks']
    regions = {'Medio Oriente': ['israel', 'iran', 'gaza', 'yemen'], 'Est Europa': ['russia', 'ukraine', 'putin', 'nato'], 'Asia-Pacifico': ['china', 'taiwan', 'beijing', 'xi']}
    region_scores, score_totale, news_items = {'Medio Oriente': 0, 'Est Europa': 0, 'Asia-Pacifico': 0}, 0, []
    for entry in feed.entries[:25]:
        titolo = entry.title.lower()
        item_score = sum(1 for w in risk_words if w in titolo) - sum(1 for w in peace_words if w in titolo)
        score_totale += item_score
        for region, keywords in regions.items():
            if any(kw in titolo for kw in keywords): region_scores[region] += 1
        if item_score != 0 and len(news_items) < 8: news_items.append({'titolo': entry.title, 'link': entry.link, 'score': item_score})
    return max(0, min(100, 50 + (score_totale * 4))), news_items, region_scores

def calcola_fase_avanzata(yc, z_sp500, tension):
    if yc < 0 or tension >= 65: return '1. Allarme Rosso (Risk-Off)'
    elif yc > 0 and (z_sp500 < 0 or tension >= 50): return '2. Incertezza / Accumulo Difensivo'
    else: return '3. Espansione (Risk-On)'

def get_telegram_link():
    return st.secrets.get("TG_BOT_URL", "https://t.me/tuobot")
