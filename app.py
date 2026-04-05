import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred
import feedparser
import google.generativeai as genai
from io import BytesIO
import urllib.request
import json

st.set_page_config(page_title="Macro Dashboard Pro", layout="wide")
st.title("📊 Global Macro, Crypto & AI Assistant")

with st.expander("📚 Legenda e Glossario Rapido"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo BTC diviso per la media a 200 giorni. < 1.0 = Accumulo. > 2.4 = Bolla.
    * **VIX (Indice della Paura):** Sopra 20 c'è nervosismo, sopra 30 c'è panico, sotto 15 c'è compiacenza.
    """)

# --- 1. MOTORE DATI MACRO (Aggiunti VIX e Petrolio) ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    assets = {'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F', 'Petrolio': 'CL=F', 'Treasury 10Y': '^TNX', 'VIX': '^VIX'}
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
    df = df.ffill().dropna()
    
    for col in ['S&P 500', 'Dollaro DXY', 'Oro', 'Petrolio', 'Treasury 10Y', 'VIX', 'Bitcoin']:
        df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    return df.dropna()

# --- 2. MOTORE ETF SCREENER ---
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
        except: continue
    return pd.DataFrame(dati)

# --- 3. MOTORE CRYPTO ALTCOIN E F&G ---
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

# --- 4. MOTORE GEOPOLITICO (Aggiornato con Regional Tracking) ---
@st.cache_data(ttl=1800)
def analyze_geopolitics():
    url = "https://news.google.com/rss/search?q=geopolitics+OR+sanctions+OR+conflict+OR+economy+markets&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    
    if not feed.entries: return 50, [], {}
        
    risk_words = ['war', 'strike', 'tariff', 'sanction', 'missile', 'tension', 'conflict', 'invasion']
    peace_words = ['peace', 'deal', 'agreement', 'ceasefire', 'talks']
    
    regions = {
        'Medio Oriente': ['israel', 'iran', 'gaza', 'yemen', 'saudi', 'lebanon', 'middle east'],
        'Est Europa': ['russia', 'ukraine', 'putin', 'nato', 'moscow', 'kiev'],
        'Asia-Pacifico': ['china', 'taiwan', 'beijing', 'xi', 'korea', 'asia']
    }
    
    region_scores = {'Medio Oriente': 0, 'Est Europa': 0, 'Asia-Pacifico': 0}
    score_totale = 0
    news_items = []
    
    for entry in feed.entries[:25]:
        titolo = entry.title.lower()
        
        # Calcolo sentiment
        item_score = sum(1 for w in risk_words if w in titolo) - sum(1 for w in peace_words if w in titolo)
        score_totale += item_score
        
        # Scansione Regionale
        for region, keywords in regions.items():
            if any(kw in titolo for kw in keywords):
                region_scores[region] += 1
                
        if item_score != 0 and len(news_items) < 8:
            news_items.append({'titolo': entry.title, 'link': entry.link, 'score': item_score})
            
    tension_index = max(0, min(100, 50 + (score_totale * 4)))
    return tension_index, news_items, region_scores

# --- INTERFACCIA E CARICAMENTO ---
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

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
        df_crypto = get_crypto_screener()
        fgi_val, fgi_class = get_crypto_fgi()
        tension_index, top_news, region_scores = analyze_geopolitics()
    except Exception as e:
        st.error(f"Errore caricamento dati base: {e}")
        st.stop()

current = df.iloc[-1]
st.sidebar.markdown("---")
st.sidebar.download_button("📥 Scarica Database in Excel", data=to_excel(df), file_name="macro_data.xlsx", mime="application/vnd.ms-excel")

def calcola_fase_avanzata(yc, z_sp500, tension):
    if yc < 0 or tension >= 65: return '1. Allarme Rosso (Risk-Off)'
    elif yc > 0 and (z_sp500 < 0 or tension >= 50): return '2. Incertezza / Accumulo Difensivo'
    else: return '3. Espansione (Risk-On)'

fase_attuale = calcola_fase_avanzata(current['YieldCurve'], current['Z_S&P 500'], tension_index)
ai_context = f"Dati live: Fase {fase_attuale}, S&P500 Z:{current['Z_S&P 500']:.2f}, Geopolitica:{tension_index}, BTC:${current['Bitcoin']:.0f}, Crypto FGI: {fgi_val}."

# --- SCHEDE ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏛️ Macro & ETF", "⚡ Crypto Pro", "🌍 Geopolitica & Radar", "🤖 AI Chatbot", "📚 Academy"])

# ----------------- SCHEDA 1 (Macro & ETF) -----------------
with tab1:
    st.header("🚦 Semaforo Macro Intelligente")
    if "1." in fase_attuale: st.error(f"🚨 **FASE ATTUALE: {fase_attuale}**")
    elif "2." in fase_attuale: st.warning(f"⚖️ **FASE ATTUALE: {fase_attuale}**")
    else: st.success(f"🚀 **FASE ATTUALE: {fase_attuale}**")
    st.markdown("---")

    col_st, col_mt, col_lt = st.columns(3)
    with col_st:
        st.subheader("⏱️ Breve Termine (1-3 Mesi)")
        if tension_index >= 60: st.error("🛡️ Focus: Geopolitica (Difesa, Cyber, Energia)")
        elif "1." in fase_attuale: st.error("🧱 Focus: Protezione (Utilities, Salute, Oro)")
        else: st.success("🔥 Focus: Momentum (Tech, Finanza)")
    with col_mt:
        st.subheader("📅 Medio Termine (6-12 Mesi)")
        if "1." in fase_attuale or "2." in fase_attuale: st.warning("📉 Focus: Taglio Tassi (Bonds, Real Estate)")
        else: st.success("🏭 Focus: Espansione (Industriali, Emergenti)")
    with col_lt:
        st.subheader("🔭 Lungo Termine (1-3 Anni)")
        st.info("🌐 Focus: Mega-Trend (AI, Transizione Energetica, Biotech)")

    st.markdown("---")
    if not df_etfs.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Geografia'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Aree Geografiche (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)
        with col_g2: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Settore'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Settori USA (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)
        st.dataframe(df_etfs[['Asset', 'Categoria', 'Prezzo ($)', 'Perf. 1 Mese (%)', 'Segnale Operativo']].sort_values(by='Perf. 1 Mese (%)', ascending=False), use_container_width=True, hide_index=True)

# ----------------- SCHEDA 2 (Crypto Pro) -----------------
with tab2:
    st.header("⚡ Crypto Cycle & Altcoin Rotation")
    mayer_btc = current['Mayer_BTC']
    col_pre1, col_pre2 = st.columns(2)
    with col_pre1:
        if mayer_btc < 1.0: st.success("🔋 **Fase: ACCUMULO (Bottom)**")
        elif mayer_btc < 2.0: st.warning("📈 **Fase: BULL MARKET (Trend sano)**")
        else: st.error("💥 **Fase: BOLLA SPECULATIVA (Euphoria)**")
    with col_pre2:
        st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=fgi_val, title={'text': f"Fear & Greed: {fgi_class}"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 45], 'color': "#e57373"}, {'range': [55, 100], 'color': "#81c784"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Prezzo BTC", f"${current['Bitcoin']:,.0f}")
    c2.metric("Mayer Multiple", f"{mayer_btc:.2f}")
    c3.metric("RSI (14 gg)", f"{current['RSI_BTC']:.0f}")
    c4.metric("Distanza da ATH", f"{current['BTC_Drawdown']:.1f}%")

    if not df_crypto.empty:
        st.plotly_chart(px.bar(df_crypto, x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Altcoin Rotation (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)

# ----------------- SCHEDA 3 (Geopolitica & Radar) -----------------
with tab3:
    st.header("🌍 Geopolitical Intelligence & Risk Radar")
    st.write("Analisi semantica e posizionamento geografico delle tensioni globali.")
    
    col_g1, col_g2, col_g3 = st.columns([1.5, 1, 1])
    
    with col_g1:
        st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=tension_index, title={'text': "Indice di Tensione Globale"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"}, {'range': [60, 100], 'color': "#e57373"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)
        
    with col_g2:
        st.subheader("🗺️ Regional Hotspots")
        st.write("Menzioni nei feed (ultime 24h):")
        for region, count in region_scores.items():
            st.metric(region, f"{count} news", delta="🔥 Caldo" if count >= 2 else "Calmo", delta_color="inverse" if count >= 2 else "normal")

    with col_g3:
        st.subheader("🛢️ Reality Check (Beni Rifugio)")
        st.write("Il mercato sta prezzando la paura?")
        st.metric("VIX (Indice Paura)", f"{current['VIX']:.1f}", help="> 20 = Nervosismo, > 30 = Panico")
        st.metric("Trend Oro (Z-Score)", f"{current['Z_Oro']:.2f}", delta="Risk-Off" if current['Z_Oro'] > 1 else "Neutro")
        st.metric("Trend Petrolio (Z-Score)", f"{current['Z_Petrolio']:.2f}", delta="Shock Supply" if current['Z_Petrolio'] > 1 else "Normale")

    st.markdown("---")
    st.subheader("📰 Ultime Notizie Analizzate")
    if top_news:
        for item in top_news:
            badge = "🔴 Tension/Risk" if item['score'] > 0 else "🟢 Peace/Deal" if item['score'] < 0 else "⚪ Neutrale"
            st.markdown(f"- **[{badge}]** [{item['titolo']}]({item['link']})")
    else:
        st.info("Nessuna notizia ad alta priorità rilevata.")

# ----------------- SCHEDA 4 (AI Chatbot) -----------------
with tab4:
    st.header("🤖 Quant AI Assistant")
    if "GEMINI_API_KEY" in st.secrets:
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-pro')
            if "chat_history" not in st.session_state: st.session_state.chat_history = []
            for m in st.session_state.chat_history: st.chat_message("user" if m["role"]=="user" else "assistant").markdown(m["content"])
            if prompt := st.chat_input("Chiedimi un'analisi..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                st.chat_message("user").markdown(prompt)
                with st.spinner("Analisi AI in corso..."):
                    response = model.generate_content(f"{ai_context}\n\nDomanda: {prompt}")
                    st.chat_message("assistant").markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
        except: st.error("Errore API. Controlla i secrets.")

# ----------------- SCHEDA 5 (Academy Educativa) -----------------
with tab5:
    st.header("📚 Macro Academy")
    st.write("Benvenuto nella sezione formativa. Clicca sui moduli qui sotto per comprendere le logiche che muovono i mercati.")

    with st.expander("🌍 1. Macroeconomia & Banche Centrali"):
        st.markdown("**Che cos'è la Macroeconomia?**\nÈ lo studio del comportamento dell'economia nel suo complesso (inflazione, disoccupazione, crescita). Il vero 'burattinaio' dei mercati è la **Banca Centrale**.\n\n**La Regola d'Oro dei Tassi di Interesse:**\n* Se l'inflazione sale troppo, la Banca Centrale **alza i tassi di interesse** -> *Il mercato azionario scende (Risk-Off).*\n* Quando l'economia frena, la Banca Centrale **taglia i tassi**. Il denaro costa poco -> *Il mercato azionario sale per i soldi facili (Risk-On).*")
    with st.expander("📈 2. Azioni & Rotazione Settoriale"):
        st.markdown("**Cos'è la Rotazione Settoriale?**\nI soldi nei mercati non dormono mai, si spostano in base al ciclo economico:\n* **Settori Ciclici (Tech, Beni di Lusso):** Vanno benissimo quando l'economia cresce.\n* **Settori Difensivi (Salute, Utilities):** Vanno bene durante le recessioni.")
    with st.expander("🏛️ 3. Obbligazioni (Bonds) & Curva dei Rendimenti"):
        st.markdown("**Il Segreto della Curva dei Rendimenti:**\nSe presti soldi a breve termine (2 anni) e ricevi un interesse più alto rispetto a prestarli a lungo termine (10 anni), la curva si **Inverte**. Questo succede perché gli investitori sono in preda al panico nel breve termine: storicamente anticipa quasi sempre una **Recessione**.")
    with st.expander("💱 4. Forex, Dollaro (DXY) e Oro"):
        st.markdown("**Relazioni importanti:**\n* Il Dollaro è il 'Bene Rifugio' mondiale. Se c'è panico, tutti comprano dollari e il DXY sale.\n* Se il Dollaro sale in modo aggressivo, di solito le Azioni e le Crypto scendono.\n* L'**Oro** è l'altro grande bene rifugio contro la svalutazione.")
    with st.expander("⚡ 5. Criptovalute, Bitcoin e Altcoins"):
        st.markdown("**L'Altcoin Season:**\nIl mercato Crypto segue un flusso ciclico:\n1. I capitali entrano nel bene più sicuro: **Bitcoin**.\n2. I profitti vengono spostati su **Ethereum**.\n3. Poi si scende alle **Layer 1** (Solana, Avalanche).\n4. Infine si arriva alla mania pura (**Memecoin**).")
