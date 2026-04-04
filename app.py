import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser

st.set_page_config(page_title="Macro Dashboard v14.0", layout="wide")
st.title("📊 Global Macro, Crypto & Social Intelligence")

# --- LEGENDA ---
with st.expander("📚 Legenda e Glossario"):
    st.markdown("""
    * **Z-Score:** Trend positivo (> 0) o negativo (< 0).
    * **Mayer Multiple:** Ciclo BTC. < 1.0 Accumulo, > 2.4 Bolla.
    * **Social Sentiment:** Analisi dei trend caldi su Reddit, X e forum finanziari.
    """)

# --- RECUPERO DATI ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    assets = {'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F', 'Petrolio': 'CL=F', 'Treasury 10Y': '^TNX'}
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="15y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
    
    btc_hist = yf.Ticker('BTC-USD').history(period="15y")
    btc_hist.index = pd.to_datetime(btc_hist.index).tz_localize(None).normalize()
    df['Bitcoin'] = btc_hist['Close']
    df['BTC_200DMA'] = df['Bitcoin'].rolling(window=200).mean()
    df['Mayer_BTC'] = df['Bitcoin'] / df['BTC_200DMA']
    
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    df = df.ffill().dropna()
    
    for col in ['S&P 500', 'Dollaro DXY', 'Oro', 'Petrolio', 'Treasury 10Y', 'Bitcoin']:
        df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    df = df.dropna()
    def assegna_fase(row):
        if row['YieldCurve'] < 0: return '1. Allarme Rosso'
        elif row['YieldCurve'] > 0 and row['Z_S&P 500'] < 0: return '2. Ripresa'
        else: return '3. Espansione'
    df['Fase_Macro'] = df.apply(assegna_fase, axis=1)
    return df

@st.cache_data(ttl=1800)
def get_social_trends():
    # Scannerizziamo i trend finanziari dai social tramite aggregatori news
    url = "https://news.google.com/rss/search?q=reddit+OR+stocktwits+OR+twitter+trending+stocks+OR+crypto+short+squeeze&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    bullish_words = ['moon', 'buy', 'undervalued', 'gem', 'breakout', 'growth', 'rally']
    bearish_words = ['crash', 'dump', 'sell', 'scam', 'bubble', 'overvalued', 'warning']
    
    social_score = 0
    trends = []
    for entry in feed.entries[:20]:
        title = entry.title.lower()
        score = sum(1 for w in bullish_words if w in title) - sum(1 for w in bearish_words if w in title)
        social_score += score
        trends.append({'titolo': entry.title, 'link': entry.link, 'sentiment': 'Bullish' if score >= 0 else 'Bearish'})
    
    gauge_val = max(0, min(100, 50 + (social_score * 5)))
    return gauge_val, trends

@st.cache_data(ttl=1800)
def analyze_geopolitics():
    url = "https://news.google.com/rss/search?q=geopolitics+OR+conflict+OR+sanctions&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    risk_words = ['war', 'missile', 'tension', 'conflict', 'invasion']
    score = sum((sum(1 for w in risk_words if w in e.title.lower())) for e in feed.entries[:20])
    return max(0, min(100, 50 + (score * 5)))

lookback = st.sidebar.slider("Z-Score Lookback", 30, 200, 90)

# --- CARICAMENTO ---
with st.spinner("🔄 Caricamento Multi-Intelligence..."):
    df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
    social_val, social_news = get_social_trends()
    tension_val = analyze_geopolitics()
    current = df.iloc[-1]

# --- SCHEDE ---
tab1, tab2, tab3, tab4 = st.tabs(["🏛️ Macro", "⚡ Crypto", "🌍 Geopolitica", "📱 Social Trends"])

with tab1:
    st.header("🚦 Semaforo Macro")
    if "1." in current['Fase_Macro']: st.error(f"🚨 {current['Fase_Macro']}")
    elif "2." in current['Fase_Macro']: st.warning(f"🔋 {current['Fase_Macro']}")
    else: st.success(f"🚀 {current['Fase_Macro']}")
    st.metric("S&P 500 Z-Score", f"{current['Z_S&P 500']:.2f}")

with tab2:
    st.header("👑 Bitcoin Cycle")
    mayer = current['Mayer_BTC']
    if mayer < 1.0: st.success("Accumulo")
    elif mayer < 2.0: st.warning("Bull Market")
    else: st.error("Bolla")
    st.metric("Mayer Multiple", f"{mayer:.2f}")

with tab3:
    st.header("🌍 Tensioni Geopolitiche")
    st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=tension_val, gauge={'axis':{'range':[0,100]}, 'steps':[{'range':[0,40],'color':"green"},{'range':[60,100],'color':"red"}]})).update_layout(height=250))

# ==========================================
# NUOVA SCHEDA 4: SOCIAL TRENDS
# ==========================================
with tab4:
    st.header("📱 Social Sentiment & Hype Scanner")
    st.write("Analisi dell'intensità e del tono dei messaggi su Reddit, X (Twitter) e StockTwits.")
    
    c_s1, c_s2 = st.columns([1, 1])
    
    with c_s1:
        if social_val > 65:
            st.error("🔥 **AVVERTIMENTO: EUFORIA SOCIAL**")
            st.markdown("Il "Retail Sentiment" è ai massimi. Tutti parlano di acquisti facili. Storicamente, questo è un segnale di possibile inversione o 'top' locale.")
        elif social_val < 35:
            st.success("❄️ **OPPORTUNITÀ: PAURA / DISINTERESSE**")
            st.markdown("Il sentiment sui social è depresso. Poco hype, molta paura. È spesso il momento migliore per gli investitori 'Contrarian'.")
        else:
            st.info("⚖️ **SENTIMENT NEUTRALE**")
            st.markdown("Non ci sono eccessi di euforia o panico sui social. Il mercato è guidato dai fondamentali.")

    with c_s2:
        fig_social = go.Figure(go.Indicator(
            mode="gauge+number", value=social_val, title={'text': "Social Hype Index"},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "black"},
                   'steps': [{'range': [0, 35], 'color': "#e57373"}, {'range': [35, 65], 'color': "#fff176"},
                             {'range': [65, 100], 'color': "#81c784"}], # Qui il verde è euforia (pericolo)
                   'threshold': {'line': {'color': "black", 'width': 4}, 'value': social_val}}))
        fig_social.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_social, use_container_width=True)

    st.subheader("📢 Trending Topics & Social News")
    for item in social_news[:10]:
        icon = "📈" if item['sentiment'] == 'Bullish' else "📉"
        st.markdown(f"{icon} [{item['titolo']}]({item['link']})")
