import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser
import google.generativeai as genai
from io import BytesIO

st.set_page_config(page_title="Macro Dashboard Pro", layout="wide")
st.title("📊 Global Macro, Crypto & AI Assistant")

with st.expander("📚 Legenda e Glossario"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo diviso per la media a 200 giorni. < 1.0 = Accumulo. > 2.4 = Bolla.
    * **RSI:** > 70 è ipercomprato (rischio calo), < 30 è ipervenduto (possibile rimbalzo).
    """)

# --- 1. MOTORE DATI MACRO ---
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

# --- 2. MOTORE ETF SCREENER (Top 10) ---
@st.cache_data(ttl=3600)
def get_etf_screener():
    tickers = {
        'USA (SPY)': 'SPY', 'Europa (VGK)': 'VGK', 'Emergenti (EEM)': 'EEM', 'Giappone (EWJ)': 'EWJ',
        'Tech (XLK)': 'XLK', 'Salute (XLV)': 'XLV', 'Finanza (XLF)': 'XLF', 'Energia (XLE)': 'XLE', 
        'Utilities (XLU)': 'XLU', 'Industria (XLI)': 'XLI'
    }
    dati = []
    for nome, tk in tickers.items():
        try:
            hist = yf.Ticker(tk).history(period="1y")
            if len(hist) > 50:
                prezzo = hist['Close'].iloc[-1]
                sma_50 = hist['Close'].tail(50).mean()
                sma_200 = hist['Close'].mean() 
                perf_1m = ((prezzo / hist['Close'].iloc[-21]) - 1) * 100
                
                if prezzo > sma_50 and sma_50 > sma_200: segnale = "🟢 Compra"
                elif prezzo > sma_50 and sma_50 <= sma_200: segnale = "🟡 Accumula"
                elif prezzo <= sma_50 and sma_50 > sma_200: segnale = "🟡 Mantieni"
                else: segnale = "🔴 Evita"
                    
                tipo = 'Geografia' if nome in ['USA (SPY)', 'Europa (VGK)', 'Emergenti (EEM)', 'Giappone (EWJ)'] else 'Settore'
                dati.append({'Categoria': tipo, 'Asset': nome, 'Prezzo ($)': round(prezzo, 2), 'Perf. 1 Mese (%)': round(perf_1m, 2), 'Segnale Operativo': segnale})
        except:
            continue
    return pd.DataFrame(dati)

# --- 3. MOTORE GEOPOLITICO E NEWS ---
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

# --- INTERFACCIA E CARICAMENTO ---
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

# Esportazione Excel
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=True, sheet_name='Data')
    writer.close()
    return output.getvalue()

with st.spinner("📊 Inizializzazione Motori Quantitativi..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        df_etfs = get_etf_screener()
        tension_index, top_news = analyze_geopolitics()
    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        st.stop()

current = df.iloc[-1]
st.sidebar.markdown("---")
st.sidebar.download_button("📥 Scarica Database in Excel", data=to_excel(df), file_name="macro_data.xlsx", mime="application/vnd.ms-excel")

def calcola_fase_avanzata(yc, z_sp500, tension):
    if yc < 0 or tension >= 65: return '1. Allarme Rosso (Risk-Off)'
    elif yc > 0 and (z_sp500 < 0 or tension >= 50): return '2. Incertezza / Accumulo Difensivo'
    else: return '3. Espansione (Risk-On)'

fase_attuale = calcola_fase_avanzata(current['YieldCurve'], current['Z_S&P 500'], tension_index)

ai_context = f"""
Sei un analista quantitativo esperto. I dati di mercato correnti:
- Fase Macro Economica: {fase_attuale}
- S&P 500 Z-Score: {current['Z_S&P 500']:.2f}
- Indice Geopolitico (0-100, >60 è rischio): {tension_index}
- Prezzo Bitcoin: ${current['Bitcoin']:.0f}
- Bitcoin Mayer Multiple (<1 accumulo, >2 bolla): {current['Mayer_BTC']:.2f}
Rispondi in modo conciso basandoti su questi dati per consigliare asset allocation.
"""

# --- SCHEDE ---
tab1, tab2, tab3, tab4 = st.tabs(["🏛️ Macro & ETF", "⚡ Crypto", "🌍 Geopolitica", "🤖 AI Chatbot"])

# ----------------- SCHEDA 1 -----------------
with tab1:
    st.header("🚦 Semaforo Macro Intelligente")
    if "1." in fase_attuale:
        st.error(f"🚨 **FASE ATTUALE: {fase_attuale}**\n\n**Ambiente:** Curva invertita o forte rischio geopolitico. Difesa massima.")
    elif "2." in fase_attuale:
        st.warning(f"⚖️ **FASE ATTUALE: {fase_attuale}**\n\n**Ambiente:** Incertezza. Falso segnale di ripresa possibile.")
    else:
        st.success(f"🚀 **FASE ATTUALE: {fase_attuale}**\n\n**Ambiente:** Clima disteso e trend rialzista solido. Propensione al rischio.")
    
    st.markdown("---")
    st.header("🗺️ Mappa dei Mercati e Rotazione Settoriale")
    
    if not df_etfs.empty:
        df_geo = df_etfs[df_etfs['Categoria'] == 'Geografia']
        df_sec = df_etfs[df_etfs['Categoria'] == 'Settore']
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_geo = px.bar(df_geo, x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale=px.colors.diverging.RdYlGn, title="Aree Geografiche (1M)")
            fig_geo.update_layout(coloraxis_showscale=False, height=300)
            st.plotly_chart(fig_geo, use_container_width=True)
        with col_g2:
            fig_sec = px.bar(df_sec, x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale=px.colors.diverging.RdYlGn, title="Settori USA (1M)")
            fig_sec.update_layout(coloraxis_showscale=False, height=300)
            st.plotly_chart(fig_sec, use_container_width=True)
            
        st.subheader("📋 Top 10 ETF Tracker (Semaforo Trend)")
        st.dataframe(df_etfs[['Asset', 'Categoria', 'Prezzo ($)', 'Perf. 1 Mese (%)', 'Segnale Operativo']].sort_values(by='Perf. 1 Mese (%)', ascending=False), use_container_width=True, hide_index=True)

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500 Z-Score", f"{current['Z_S&P 500']:.2f}")
    c2.metric("Dollaro DXY", f"{current['Z_Dollaro DXY']:.2f}")
    c3.metric("Oro", f"{current['Z_Oro']:.2f}")
    c4.metric("Treasury 10Y", f"{current['Z_Treasury 10Y']:.2f}")

# ----------------- SCHEDA 2 -----------------
with tab2:
    st.header("👑 Bitcoin (BTC) & Ecosistema")
    mayer_btc = current['Mayer_BTC']
    if mayer_btc < 1.0: st.success("🔋 **Fase del Ciclo BTC: Accumulo (Bear / Early Bull)**\n\nSolo BTC ed ETH. Evita Memecoin.")
    elif mayer_btc < 2.0: st.warning("📈 **Fase del Ciclo BTC: Bull Market (Mid Cycle)**\n\nRotazione verso Layer 1 e DeFi.")
    else: st.error("💥 **Fase del Ciclo BTC: Bolla Speculativa (Euphoria)**\n\nRischio altissimo. Accumula Stablecoin.")

    col_b1, col_b2, col_b3 = st.columns(3)
    col_b1.metric("Prezzo BTC", f"${current['Bitcoin']:,.0f}")
    col_b2.metric("Mayer Multiple", f"{mayer_btc:.2f}")
    col_b3.metric("RSI (14 gg)", f"{current['RSI_BTC']:.0f}")

# ----------------- SCHEDA 3 -----------------
with tab3:
    st.header("🌍 Geopolitical News Scanner")
    col_g1, col_g2 = st.columns([1, 1])
    with col_g1:
        if tension_index < 40: st.success("🟢 **Stato: Distensione Globale**")
        elif tension_index <= 60: st.warning("🟡 **Stato: Tensione Normale**")
        else: st.error("🔴 **Stato: Allarme Geopolitico (Risk-Off)**")
    with col_g2:
        fig_geo = go.Figure(go.Indicator(mode="gauge+number", value=tension_index, title={'text': "Indice Tensione"},
            gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"}, {'range': [60, 100], 'color': "#e57373"}]}))
        fig_geo.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_geo, use_container_width=True)

# ----------------- SCHEDA 4 -----------------
with tab4:
    st.header("🤖 Quant AI Assistant (Powered by Gemini)")
    st.write("Analizza i dati in tempo reale del cruscotto e ti risponde come un analista professionista.")
    
    if "GEMINI_API_KEY" not in st.secrets:
        st.warning("⚠️ Manca la GEMINI_API_KEY nei Secrets di Streamlit! Inseriscila per usare la chat.")
    else:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Usiamo gemini-pro che non ha problemi di versione
        model = genai.GenerativeModel('gemini-pro')

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for message in st.session_state.chat_history:
            if message["role"] != "system":
                with st.chat_message("user" if message["role"] == "user" else "assistant"):
                    st.markdown(message["content"])

        if prompt := st.chat_input("Chiedimi un parere sull'allocazione attuale..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("Analisi AI in corso..."):
                try:
                    full_prompt = f"{ai_context}\n\nDomanda dell'utente: {prompt}"
                    response = model.generate_content(full_prompt)
                    with st.chat_message("assistant"):
                        st.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Errore API: {e}")
