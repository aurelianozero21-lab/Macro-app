import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser
from io import BytesIO

st.set_page_config(page_title="Macro Dashboard v14.1", layout="wide")
st.title("📊 Global Macro, Crypto & Social Intelligence")

# --- RECUPERO DATI ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    assets = {'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F', 'Petrolio': 'CL=F', 'Treasury 10Y': '^TNX', 'Bitcoin': 'BTC-USD'}
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="15y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
    
    df['BTC_200DMA'] = df['Bitcoin'].rolling(window=200).mean()
    df['Mayer_BTC'] = df['Bitcoin'] / df['BTC_200DMA']
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    df = df.ffill().dropna()
    
    for col in ['S&P 500', 'Dollaro DXY', 'Oro', 'Petrolio', 'Treasury 10Y', 'Bitcoin']:
        df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    def assegna_fase(row):
        if row['YieldCurve'] < 0: return '1. Allarme Rosso'
        elif row['YieldCurve'] > 0 and row['Z_S&P 500'] < 0: return '2. Ripresa'
        else: return '3. Espansione'
    df['Fase_Macro'] = df.apply(assegna_fase, axis=1)
    return df.dropna()

@st.cache_data(ttl=1800)
def get_social_trends():
    url = "https://news.google.com/rss/search?q=reddit+OR+stocktwits+OR+twitter+trending+stocks&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    bullish = ['moon', 'buy', 'undervalued', 'gem', 'breakout', 'growth']
    bearish = ['crash', 'dump', 'sell', 'scam', 'bubble', 'warning']
    score_raw = 0
    trends = []
    for entry in feed.entries[:15]:
        t = entry.title.lower()
        s = sum(1 for w in bullish if w in t) - sum(1 for w in bearish if w in t)
        score_raw += s
        trends.append({'titolo': entry.title, 'link': entry.link, 'sent': 'Bullish' if s >= 0 else 'Bearish'})
    return max(0, min(100, 50 + (score_raw * 5))), trends

lookback = st.sidebar.slider("Z-Score Lookback", 30, 200, 90)

# --- CARICAMENTO ---
with st.spinner("🔄 Sincronizzazione Intelligence..."):
    try:
        df_final = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        social_val, social_news = get_social_trends()
        current = df_final.iloc[-1]
    except Exception as e:
        st.error(f"Errore: {e}")
        st.stop()

# --- TASTO EXPORT EXCEL NELLA SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Export Dati")
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=True, sheet_name='Data')
    writer.close()
    return output.getvalue()

st.sidebar.download_button(
    label="📥 Scarica Database in Excel",
    data=to_excel(df_final),
    file_name="macro_intelligence_data.xlsx",
    mime="application/vnd.ms-excel"
)

# --- SCHEDE ---
t1, t2, t3 = st.tabs(["🏛️ Macro & Crypto", "🌍 Geopolitica", "📱 Social Hype"])

with t1:
    st.header("🚦 Market Status")
    if "1." in current['Fase_Macro']: st.error(f"FASE: {current['Fase_Macro']}")
    else: st.success(f"FASE: {current['Fase_Macro']}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("S&P 500 Z-Score", f"{current['Z_S&P 500']:.2f}")
    c2.metric("Mayer Multiple (BTC)", f"{current['Mayer_BTC']:.2f}")
    c3.metric("Yield Curve", f"{current['YieldCurve']:.2f}")

with t2:
    st.header("🌍 Geopolitica")
    st.info("Analisi delle tensioni internazionali basata sui feed news.")

with t3:
    st.header("📱 Social Intelligence")
    # NOTA: Qui ho corretto le virgolette per evitare il SyntaxError
    if social_val > 65:
        st.error("🔥 **AVVERTIMENTO: EUFORIA SOCIAL**")
        st.write("Il sentiment dei piccoli investitori (Retail) è ai massimi. Storicamente un segnale di pericolo.")
    elif social_val < 35:
        st.success("❄️ **OPPORTUNITÀ: PAURA**")
        st.write("C'è pessimismo sui social: ottimo momento per acquisti contrarian.")
    else:
        st.info("⚖️ **SENTIMENT NEUTRALE**")

    st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=social_val, title={'text': "Social Hype Index"}, 
                    gauge={'axis':{'range':[0,100]}, 'steps':[{'range':[0,35],'color':"red"},{'range':[65,100],'color':"green"}]})).update_layout(height=300))
    
    for item in social_news:
        st.markdown(f"- [{item['sent']}] [{item['titolo']}]({item['link']})")
