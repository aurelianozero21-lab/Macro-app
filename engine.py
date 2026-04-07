import yfinance as yf
import pandas as pd
from fredapi import Fred
import feedparser
import urllib.request
import json
import streamlit as st
import datetime

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

def init_supabase():
    if SUPABASE_AVAILABLE and "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    return None

@st.cache_data(ttl=120)
def get_live_prices():
    tickers = ['^GSPC', 'BTC-USD', 'GC=F', '^VIX', 'CL=F']
    prices = {'^GSPC': 0, 'BTC-USD': 0, 'GC=F': 0, '^VIX': 0, 'CL=F': 0}
    try:
        data = yf.download(tickers, period="1d", interval="2m", progress=False)
        if not data.empty and 'Close' in data:
            for t in tickers:
                prices[t] = data['Close'][t].dropna().iloc[-1].item()
    except:
        pass
    return prices

@st.cache_data(ttl=86400)
def get_shiller_pe():
    try:
        url = 'https://www.multpl.com/shiller-pe/table/by-month'
        tables = pd.read_html(url)
        df_cape = tables[0]
        df_cape.columns = ['Date', 'CAPE']
        df_cape['Date'] = pd.to_datetime(df_cape['Date'])
        df_cape['CAPE'] = df_cape['CAPE'].astype(str).str.extract(r'([0-9.]+)').astype(float)
        df_cape.set_index('Date', inplace=True)
        df_cape = df_cape.sort_index().resample('D').ffill()
        return df_cape['CAPE']
    except Exception as e:
        return pd.Series(dtype=float)

@st.cache_data(ttl=7200)
def load_all_data(api_key, lookback):
    tickers_map = {
        'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F', 
        'Treasury 10Y': '^TNX', 'High Yield': 'HYG', 'VIX': '^VIX', 
        'Bond ETF': 'IEF', 'Bitcoin': 'BTC-USD'
    }
    
    df = pd.DataFrame()
    
    try:
        lista_tickers = list(tickers_map.values())
        data = yf.download(lista_tickers, period="15y", progress=False)
        
        if 'Close' in data:
            for nome, ticker in tickers_map.items():
                serie = data['Close'][ticker].dropna()
                serie.index = pd.to_datetime(serie.index).tz_localize(None).normalize()
                df[nome] = serie
    except Exception as e:
        st.error(f"Errore Yahoo Finance: {e}")
        return pd.DataFrame()
            
    df['BTC_ATH'] = df['Bitcoin'].cummax()
    df['BTC_Drawdown'] = ((df['Bitcoin'] - df['BTC_ATH']) / df['BTC_ATH']) * 100
    df['BTC_200DMA'] = df['Bitcoin'].rolling(window=200).mean()
    df['Mayer_BTC'] = df['Bitcoin'] / df['BTC_200DMA']
    
    delta_btc = df['Bitcoin'].diff()
    rs_btc = (delta_btc.where(delta_btc > 0, 0)).rolling(window=14).mean() / (-delta_btc.where(delta_btc < 0, 0)).rolling(window=14).mean()
    df['RSI_BTC'] = 100 - (100 / (1 + rs_btc))
    
    try:
        fred = Fred(api_key=api_key)
        df['YieldCurve'] = fred.get_series('T10Y2Y')
    except:
        df['YieldCurve'] = 0.0

    try:
        fred = Fred(api_key=api_key)
        df['WALCL'] = fred.get_series('WALCL')
        df['WTREGEN'] = fred.get_series('WTREGEN')
        df['RRPONTSYD'] = fred.get_series('RRPONTSYD')
        df['Fed_Liquidity_T'] = (df['WALCL'] / 1000000) - (df['WTREGEN'] / 1000000) - (df['RRPONTSYD'] / 1000)
    except:
        df['Fed_Liquidity_T'] = 0.0
        
    df['Liquidity_Delta_30d'] = df['Fed_Liquidity_T'].diff(periods=21)
    
    cape_series = get_shiller_pe()
    if not cape_series.empty:
        df['CAPE'] = cape_series
    else:
        df['CAPE'] = 30.0
        
    df = df.ffill().dropna()
    
    cols_to_z = ['S&P 500', 'Dollaro DXY', 'Oro', 'Treasury 10Y', 'Bitcoin', 'High Yield', 'VIX', 'Fed_Liquidity_T', 'CAPE']
    for col in cols_to_z:
        if col in df.columns:
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

# --- NUOVA FUNZIONE: SMART ALERTS ---
def check_smart_alerts(df, live_prices, tension_index):
    alerts = []
    
    if df.empty:
        return alerts
        
    current = df.iloc[-1]
    
    # 1. Alert Volatilità Estrema
    vix_live = live_prices.get('^VIX', current.get('VIX', 0))
    if vix_live > 28:
        alerts.append("🚨 PANICO SUI MERCATI: Il VIX ha superato quota 28. Possibile crash azionario in corso.")
        
    # 2. Alert Rischio Geopolitico
    if tension_index >= 70:
        alerts.append("🔥 ALLARME GEOPOLITICA: Indice di tensione alle stelle (>70). Controlla il prezzo dell'Oro e del Petrolio.")
        
    # 3. Alert Divergenza Smart Money
    if current.get('Z_S&P 500', 0) > 0 and current.get('Z_High Yield', 0) < -1:
        alerts.append("⚠️ DIVERGENZA FATALE: L'S&P 500 sta salendo ma il mercato del credito spazzatura sta crollando. Le banche stanno uscendo.")
        
    # 4. Alert Crypto Flash Crash / Pump
    btc_live = live_prices.get('BTC-USD', current.get('Bitcoin', 0))
    try:
        btc_ieri = df['Bitcoin'].iloc[-2]
        variazione_btc = ((btc_live - btc_ieri) / btc_ieri) * 100
        if variazione_btc < -7:
            alerts.append(f"🩸 CRYPTO CRASH: Bitcoin sta perdendo oltre il 7% oggi ({variazione_btc:.1f}%).")
        elif variazione_btc > 7:
            alerts.append(f"🚀 CRYPTO PUMP: Bitcoin in volo di oltre il 7% oggi ({variazione_btc:.1f}%).")
    except:
        pass
        
    # 5. Alert Inversione Curva dei Rendimenti
    try:
        yc_oggi = df['YieldCurve'].iloc[-1]
        yc_ieri = df['YieldCurve'].iloc[-2]
        if yc_ieri > 0 and yc_oggi < 0:
            alerts.append("☠️ INVERSIONE DELLA CURVA: I tassi a 2 anni hanno appena superato i decennali. Il timer della recessione è partito.")
    except:
        pass
        
    return alerts

@st.cache_data(ttl=7200)
def get_etf_screener():
    tickers = {'USA (SPY)': 'SPY', 'Europa (VGK)': 'VGK', 'Emergenti (EEM)': 'EEM', 'Giappone (EWJ)': 'EWJ', 'Tech (XLK)': 'XLK', 'Salute (XLV)': 'XLV', 'Finanza (XLF)': 'XLF', 'Energia (XLE)': 'XLE', 'Utilities (XLU)': 'XLU', 'Industria (XLI)': 'XLI'}
    dati = []
    try:
        lista_tk = list(tickers.values())
        data = yf.download(lista_tk, period="1y", progress=False)
        if 'Close' in data:
            for nome, tk in tickers.items():
                hist = data['Close'][tk].dropna()
                if len(hist) > 50:
                    prezzo, sma_50, sma_200 = hist.iloc[-1], hist.tail(50).mean(), hist.mean() 
                    perf_1m = ((prezzo / hist.iloc[-21]) - 1) * 100
                    segnale = "🟢 Compra" if prezzo > sma_50 and sma_50 > sma_200 else "🟡 Accumula" if prezzo > sma_50 else "🔴 Evita"
                    tipo = 'Geografia' if tk in ['SPY', 'VGK', 'EEM', 'EWJ'] else 'Settore'
                    dati.append({'Categoria': tipo, 'Asset': nome, 'Prezzo ($)': round(prezzo, 2), 'Perf. 1 Mese (%)': round(perf_1m, 2), 'Segnale Operativo': segnale})
    except: pass
    return pd.DataFrame(dati)

@st.cache_data(ttl=7200)
def get_crypto_screener():
    tickers = {'Bitcoin': 'BTC-USD', 'Ethereum': 'ETH-USD', 'Solana': 'SOL-USD', 'Binance': 'BNB-USD', 'Avalanche': 'AVAX-USD'}
    dati = []
    try:
        data = yf.download(list(tickers.values()), period="1y", progress=False)
        if 'Close' in data:
            for nome, tk in tickers.items():
                hist = data['Close'][tk].dropna()
                if len(hist) > 50:
                    prezzo, sma_50, sma_200 = hist.iloc[-1], hist.tail(50).mean(), hist.mean() 
                    perf_1m = ((prezzo / hist.iloc[-21]) - 1) * 100
                    dati.append({'Asset': nome, 'Prezzo ($)': round(prezzo, 2), 'Perf. 1 Mese (%)': round(perf_1m, 2)})
    except: pass
    return pd.DataFrame(dati)

@st.cache_data(ttl=3600)
def get_crypto_fgi():
    try:
        with urllib.request.urlopen("https://api.alternative.me/fng/") as url:
            data = json.loads(url.read().decode())
            return int(data['data'][0]['value']), data['data'][0]['value_classification']
    except: return 50, "Neutral"

@st.cache_data(ttl=3600)
def analyze_geopolitics():
    url = "https://news.google.com/rss/search?q=geopolitics+OR+sanctions+OR+conflict+OR+economy+markets&hl=en-US&gl=US&ceid=US:en"
    try:
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
    except:
        return 50, [], {}

def calcola_fase_avanzata(yc, z_sp500, tension):
    if yc < 0 or tension >= 65: return '1. Allarme Rosso (Risk-Off)'
    elif yc > 0 and (z_sp500 < 0 or tension >= 50): return '2. Incertezza / Accumulo Difensivo'
    else: return '3. Espansione (Risk-On)'

def get_telegram_link():
    return st.secrets.get("TG_BOT_URL", "https://t.me/tuobot")
