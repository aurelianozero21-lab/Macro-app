import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser
import google.generativeai as genai

st.set_page_config(page_title="Macro Dashboard v15.0", layout="wide")
st.title("📊 Global Macro, Crypto & Real AI Assistant")

with st.expander("📚 Legenda e Glossario"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo diviso per la media a 200 giorni. < 1.0 = Accumulo. > 2.4 = Bolla.
    * **RSI:** > 70 è ipercomprato (rischio calo), < 30 è ipervenduto (possibile rimbalzo).
    """)

@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    assets = {'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F', 'Treasury 10Y': '^TNX'}
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
    
    delta_btc = df['Bitcoin'].diff()
    rs_btc = (delta_btc.where(delta_btc > 0, 0)).rolling(window=14).mean() / (-delta_btc.where(delta_btc < 0, 0)).rolling(window=14).mean()
    df['RSI_BTC'] = 100 - (100 / (1 + rs_btc))
    
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    df = df.ffill().dropna()
    
    for col in ['S&P 500', 'Dollaro DXY', 'Oro', 'Treasury 10Y', 'Bitcoin']:
        df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    return df.dropna()

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

lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

df = pd.DataFrame()
tension_index, top_news = 50, []

with st.spinner("📊 Sincronizzazione Dati in corso..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        tension_index, top_news = analyze_geopolitics()
    except Exception as e:
        st.error("Errore nel caricamento dei dati base.")
        st.stop()

current = df.iloc[-1]

def calcola_fase_avanzata(yc, z_sp500, tension):
    if yc < 0 or tension >= 65: return '1. Allarme Rosso (Risk-Off)'
    elif yc > 0 and (z_sp500 < 0 or tension >= 50): return '2. Incertezza / Accumulo Difensivo'
    else: return '3. Espansione (Risk-On)'

fase_attuale = calcola_fase_avanzata(current['YieldCurve'], current['Z_S&P 500'], tension_index)

# CONTESTO PER L'AI (Iniettiamo i dati live nel prompt di sistema)
ai_context = f"""
Sei un analista quantitativo esperto. Rispondi alle domande in modo conciso e professionale.
Attualmente i dati della dashboard sono:
- Fase Macro Economica: {fase_attuale}
- S&P 500 Z-Score: {current['Z_S&P 500']:.2f}
- Indice Geopolitico (0-100, >60 è rischio): {tension_index}
- Prezzo Bitcoin: ${current['Bitcoin']:.0f}
- Bitcoin Mayer Multiple (<1 accumulo, >2 bolla): {current['Mayer_BTC']:.2f}
Usa questi dati per contestualizzare le tue risposte se l'utente ti chiede consigli di mercato.
"""

tab1, tab2, tab3, tab4 = st.tabs(["🏛️ Macro & TradFi", "⚡ Crypto", "🌍 Geopolitica", "🤖 AI Quant Assistant"])

with tab1:
    st.header("🚦 Semaforo Macro Intelligente")
    if "1." in fase_attuale:
        st.error(f"🚨 **FASE ATTUALE: {fase_attuale}**\n\n**Settori:** Difesa, Oro, Dollaro USA, Utilities.")
    elif "2." in fase_attuale:
        st.warning(f"⚖️ **FASE ATTUALE: {fase_attuale}**\n\n**Settori:** Consumi di base, Cash, Tech.")
    else:
        st.success(f"🚀 **FASE ATTUALE: {fase_attuale}**\n\n**Settori:** Industriali, Finanza, Rischio.")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500 Z-Score", f"{current['Z_S&P 500']:.2f}")
    c2.metric("Dollaro DXY", f"{current['Z_Dollaro DXY']:.2f}")
    c3.metric("Oro", f"{current['Z_Oro']:.2f}")
    c4.metric("Treasury 10Y", f"{current['Z_Treasury 10Y']:.2f}")

with tab2:
    st.header("👑 Bitcoin (BTC)")
    mayer_btc = current['Mayer_BTC']
    if mayer_btc < 1.0: st.success("🔋 **Fase del Ciclo BTC: Accumulo (Bear / Early Bull)**")
    elif mayer_btc < 2.0: st.warning("📈 **Fase del Ciclo BTC: Bull Market (Mid Cycle)**")
    else: st.error("💥 **Fase del Ciclo BTC: Bolla Speculativa (Euphoria)**")

    col_b1, col_b2, col_b3 = st.columns(3)
    col_b1.metric("Prezzo BTC", f"${current['Bitcoin']:,.0f}")
    col_b2.metric("Mayer Multiple", f"{mayer_btc:.2f}")
    col_b3.metric("RSI (14 gg)", f"{current['RSI_BTC']:.0f}")

with tab3:
    st.header("🌍 Geopolitical News Scanner")
    col_g1, col_g2 = st.columns([1, 1])
    with col_g1:
        if tension_index < 40: st.success("🟢 **Stato: Distensione Globale**")
        elif tension_index <= 60: st.warning("🟡 **Stato: Tensione Normale**")
        else: st.error("🔴 **Stato: Allarme Geopolitico (Risk-Off)**")
    with col_g2:
        fig_geo = go.Figure(go.Indicator(mode="gauge+number", value=tension_index, title={'text': "Indice di Tensione"},
            gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"}, {'range': [60, 100], 'color': "#e57373"}]}))
        fig_geo.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_geo, use_container_width=True)

with tab4:
    st.header("🤖 Quant AI Assistant (Powered by Gemini)")
    st.write("Analizza i dati in tempo reale del cruscotto e ti risponde come un analista professionista.")
    
    if "GEMINI_API_KEY" not in st.secrets:
        st.warning("⚠️ Manca la GEMINI_API_KEY nei Secrets di Streamlit! Inseriscila per usare la chat.")
    else:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=ai_context)

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Chiedimi un parere sull'allocazione attuale del portafoglio..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("L'AI sta analizzando i mercati..."):
                try:
                    # Inviamo lo storico per mantenere il contesto della conversazione
                    formatted_history = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in st.session_state.chat_history[:-1]]
                    chat = model.start_chat(history=formatted_history)
                    response = chat.send_message(prompt)
                    
                    with st.chat_message("assistant"):
                        st.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Errore API: {e}")
