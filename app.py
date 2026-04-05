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
import requests
from datetime import datetime

st.set_page_config(page_title="Macro Dashboard Pro", layout="wide")
st.title("📊 Global Macro, Crypto & AI Assistant")

with st.expander("📚 Legenda e Glossario Rapido"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo BTC diviso per la media a 200 giorni. < 1.0 = Accumulo. > 2.4 = Bolla.
    * **Crypto Fear & Greed:** Misura il sentiment crypto da 0 (Panico) a 100 (Euforia).
    * **Smart Money (HYG):** Gli High Yield Bonds. Se scendono mentre la borsa sale, i grandi capitali fuggono dal rischio.
    """)

# --- MOTORI DI CALCOLO ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    assets = {'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F', 'Treasury 10Y': '^TNX', 'High Yield': 'HYG', 'VIX': '^VIX'}
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
    
    for col in ['S&P 500', 'Dollaro DXY', 'Oro', 'Treasury 10Y', 'Bitcoin', 'High Yield', 'VIX']:
        df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    return df.dropna()

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

# --- INIZIALIZZAZIONE DATI ---
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

with st.spinner("📊 Inizializzazione Motori Quantitativi..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        df_etfs = get_etf_screener()
        df_crypto = get_crypto_screener()
        fgi_val, fgi_class = get_crypto_fgi()
        tension_index, top_news, region_scores = analyze_geopolitics()
        current = df.iloc[-1]
    except Exception as e:
        st.error(f"Errore caricamento dati base: {e}")
        st.stop()

def calcola_fase_avanzata(yc, z_sp500, tension):
    if yc < 0 or tension >= 65: return '1. Allarme Rosso (Risk-Off)'
    elif yc > 0 and (z_sp500 < 0 or tension >= 50): return '2. Incertezza / Accumulo Difensivo'
    else: return '3. Espansione (Risk-On)'

fase_attuale = calcola_fase_avanzata(current['YieldCurve'], current['Z_S&P 500'], tension_index)
ai_context = f"Dati live - Fase: {fase_attuale}, S&P500 Z:{current['Z_S&P 500']:.2f}, Oro Z:{current['Z_Oro']:.2f}, Geopolitica:{tension_index}/100, BTC:${current['Bitcoin']:.0f}, BTC Mayer:{current['Mayer_BTC']:.2f}, Crypto FGI: {fgi_val}/100."

# --- SIDEBAR: EXPORT E MORNING BRIEF ---
st.sidebar.markdown("---")
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=True, sheet_name='Data')
    writer.close()
    return output.getvalue()

st.sidebar.download_button("📥 Scarica Database Excel", data=to_excel(df), file_name="macro_data.xlsx", mime="application/vnd.ms-excel")
st.sidebar.markdown("---")
st.sidebar.subheader("🗞️ Morning Briefing AI")

if "morning_brief" not in st.session_state: st.session_state.morning_brief = ""
if st.sidebar.button("🤖 Genera Report"):
    if "GEMINI_API_KEY" in st.secrets:
        with st.sidebar.status("✍️ Stesura report..."):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                modelli = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                mod = next((m for m in modelli if "flash" in m.lower() or "pro" in m.lower()), modelli[0])
                model = genai.GenerativeModel(mod)
                prompt_report = f"Sei un CIO. Scrivi un Morning Brief basato su questi dati: {ai_context}. Struttura: Sintesi, Macro, Crypto, Geopolitica. Tono istituzionale, in Markdown."
                st.session_state.morning_brief = model.generate_content(prompt_report).text
            except Exception as e: st.error(e)
    else: st.sidebar.warning("Manca API Key.")

if st.session_state.morning_brief:
    with st.sidebar.expander("📄 Visualizza Report", expanded=True):
        st.markdown(st.session_state.morning_brief)
        st.download_button("💾 Scarica (.md)", data=st.session_state.morning_brief, file_name=f"Brief_{datetime.now().strftime('%Y%m%d')}.md")

# --- NUOVO MODULO SIDEBAR: TELEGRAM ALERTS (SAAS UX RIPARATA) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Alert su Telegram")

allerte_attive = []
if "1." in fase_attuale: allerte_attive.append("🚨 *MACRO:* FASE 1 - Allarme Rosso (Risk-Off).")
if current['VIX'] > 25: allerte_attive.append(f"😱 *VIX:* Alta volatilità rilevata ({current['VIX']:.1f}).")
if current['Z_S&P 500'] > 0 and current['Z_High Yield'] < 0: allerte_attive.append("⚠️ *SMART MONEY:* Divergenza ribassista su HYG.")
if fgi_val <= 25: allerte_attive.append(f"❄️ *CRYPTO:* Paura Estrema ({fgi_val}/100).")

if not allerte_attive:
    st.sidebar.success("✅ Nessuna anomalia critica rilevata.")
else:
    for al in allerte_attive:
        st.sidebar.error(al.replace("*", ""))
        
    with st.sidebar.expander("📲 Ricevi Alert (Client Mode)"):
        st.markdown("Ricevi queste notifiche direttamente sul tuo telefono.")
        bot_url = st.secrets.get("TG_BOT_URL", "https://t.me/Inserisci_Qui_Il_Tuo_Bot")
        st.markdown(f"**Passo 1:** Apri il nostro Bot Ufficiale cliccando [👉 QUI]({bot_url}) e premi **Avvia** (fondamentale per l'anti-spam).")
        st.markdown("**Passo 2:** Clicca [👉 QUI](https://t.me/getmyid_bot) per ottenere il tuo codice ID numerico.")
        
        tg_chat = st.text_input("Passo 3: Incolla il tuo ID qui:")
        
        if st.button("🔔 Attiva Notifiche", use_container_width=True):
            if "TG_TOKEN" in st.secrets:
                if tg_chat:
                    messaggio = f"📊 *Macro Dashboard - Alert*\n{datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n" + "\n".join(allerte_attive)
                    url = f"https://api.telegram.org/bot{st.secrets['TG_TOKEN']}/sendMessage"
                    try:
                        res = requests.post(url, json={"chat_id": tg_chat, "text": messaggio, "parse_mode": "Markdown"})
                        if res.status_code == 200:
                            st.success("✅ Alert inviato con successo al tuo telefono!")
                        else:
                            st.error(f"❌ Errore (Codice {res.status_code}): Il bot non può scriverti. Assicurati di aver eseguito il Passo 1 per sbloccare l'anti-spam!")
                    except Exception as e:
                        st.error(f"Errore di rete: {e}")
                else:
                    st.warning("Inserisci il tuo ID Telegram prima di attivare.")
            else:
                st.error("⚠️ Errore di Sistema: L'amministratore non ha configurato il Bot Ufficiale (TG_TOKEN mancante).")

# --- SCHEDE ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏛️ Macro", "⚡ Crypto", "🌍 Geopolitica", "🔥 Stress Test", "🤖 AI Chatbot", "📚 Academy"])

# ----------------- SCHEDA 1 (Macro + Smart Money Radar) -----------------
with tab1:
    st.header("🚦 Semaforo Macro Intelligente")
    if "1." in fase_attuale: st.error(f"🚨 **FASE ATTUALE: {fase_attuale}**")
    elif "2." in fase_attuale: st.warning(f"⚖️ **FASE ATTUALE: {fase_attuale}**")
    else: st.success(f"🚀 **FASE ATTUALE: {fase_attuale}**")
    
    st.markdown("---")
    st.header("👁️ Smart Money Radar (Mercato Istituzionale)")
    st.write("Analisi delle divergenze tra il mercato Retail (Azioni) e i flussi Istituzionali (Credito e Volatilità).")
    
    col_sm1, col_sm2 = st.columns(2)
    with col_sm1:
        st.subheader("🏦 Rischio di Credito (HYG)")
        if current['Z_S&P 500'] > 0 and current['Z_High Yield'] < 0:
            st.error("⚠️ **DIVERGENZA RIBASSISTA (WARNING)**\n\nL'S&P 500 sale, ma le obbligazioni spazzatura scendono. I grandi fondi stanno vendendo rischio di nascosto.")
        elif current['Z_S&P 500'] < 0 and current['Z_High Yield'] > 0:
            st.success("🟢 **DIVERGENZA RIALZISTA**\n\nL'S&P 500 scende, ma lo Smart Money sta comprando credito. Possibile rimbalzo in arrivo.")
        else:
            st.info("⚖️ **CONVERGENZA (Trend Sano)**\n\nMercato azionario e credito si muovono insieme. Nessun segnale occulto.")
            
    with col_sm2:
        st.subheader("📉 Indice della Paura (VIX)")
        if current['VIX'] < 15: st.warning(f"😴 **Compiacenza Estrema ({current['VIX']:.1f})**\n\nMercato fin troppo tranquillo. Rischio di correzioni improvvise.")
        elif current['VIX'] > 25: st.error(f"😱 **Panico e Alta Volatilità ({current['VIX']:.1f})**\n\nIl mercato sta prezzando eventi critici. Entrate strategiche se il panico rientra.")
        else: st.success(f"✅ **Volatilità Normale ({current['VIX']:.1f})**\n\nNessuno stress sistemico rilevato.")

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
    st.header("🗺️ Mappa dei Mercati e Rotazione Settoriale")
    if not df_etfs.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Geografia'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Aree Geografiche (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)
        with col_g2: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Settore'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Settori USA (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)
        st.dataframe(df_etfs[['Asset', 'Categoria', 'Prezzo ($)', 'Perf. 1 Mese (%)', 'Segnale Operativo']].sort_values(by='Perf. 1 Mese (%)', ascending=False), use_container_width=True, hide_index=True)

# ----------------- SCHEDA 2 (Crypto) -----------------
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Prezzo BTC", f"${current['Bitcoin']:,.0f}")
    c2.metric("Mayer Multiple", f"{mayer_btc:.2f}")
    c3.metric("RSI (14 gg)", f"{current['RSI_BTC']:.0f}")
    c4.metric("Distanza da ATH", f"{current['BTC_Drawdown']:.1f}%")

    if not df_crypto.empty:
        st.plotly_chart(px.bar(df_crypto, x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Altcoin Rotation (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)

# ----------------- SCHEDA 3 (Geopolitica) -----------------
with tab3:
    st.header("🌍 Geopolitical Intelligence")
    col_g1, col_g2, col_g3 = st.columns([1.5, 1, 1])
    with col_g1:
        st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=tension_index, title={'text': "Tensione Globale"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"}, {'range': [60, 100], 'color': "#e57373"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)
    with col_g2:
        st.subheader("🗺️ Hotspots")
        for region, count in region_scores.items(): st.metric(region, f"{count} news", delta="🔥 Caldo" if count >= 2 else "Calmo", delta_color="inverse" if count >= 2 else "normal")
    with col_g3:
        st.subheader("🛢️ Reality Check")
        st.metric("Trend Oro (Z-Score)", f"{current['Z_Oro']:.2f}", delta="Risk-Off" if current['Z_Oro'] > 1 else "Neutro")

    st.markdown("---")
    st.subheader("📰 Ultime Notizie Analizzate")
    if top_news:
        for item in top_news:
            st.markdown(f"- **[{'🔴 Tension' if item['score'] > 0 else '🟢 Peace'}]** [{item['titolo']}]({item['link']})")

# ----------------- SCHEDA 4 (🔥 STRESS TEST PORTAFOGLIO) -----------------
with tab4:
    st.header("🔥 Stress Test & Ottimizzazione Portafoglio")
    st.write("Inserisci la tua allocazione attuale. L'IA la testerà contro i dati di mercato per scovare vulnerabilità.")
    
    st.markdown("### 💼 La tua Allocazione")
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1: alloc_azioni = st.number_input("Azioni / ETF (%)", min_value=0, max_value=100, value=50)
    with col_p2: alloc_obbligazioni = st.number_input("Obbligazioni (%)", min_value=0, max_value=100, value=20)
    with col_p3: alloc_crypto = st.number_input("Criptovalute (%)", min_value=0, max_value=100, value=10)
    with col_p4: alloc_difesa = st.number_input("Oro / Cash (%)", min_value=0, max_value=100, value=20)
    
    totale = alloc_azioni + alloc_obbligazioni + alloc_crypto + alloc_difesa
    if totale != 100: st.warning(f"⚠️ Il totale fa {totale}%. Fai quadrare a 100% per un'analisi perfetta.")
    
    if st.button("🚀 Esegui Stress Test con AI", use_container_width=True):
        if "GEMINI_API_KEY" in st.secrets:
            with st.spinner("Il Risk Manager AI sta analizzando il portafoglio..."):
                try:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    modelli = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    mod = next((m for m in modelli if "flash" in m.lower() or "pro" in m.lower()), modelli[0])
                    model = genai.GenerativeModel(mod)
                    
                    prompt_stress = f"""Sei un Risk Manager istituzionale. Portafoglio: {alloc_azioni}% Azioni, {alloc_obbligazioni}% Bond, {alloc_crypto}% Crypto, {alloc_difesa}% Oro/Cash. Macro OGGI: {ai_context}. Scrivi un report di Stress Test in Markdown (Valutazione Rischio, Breve, Medio, Lungo termine, Ottimizzazione)."""
                    risposta_stress = model.generate_content(prompt_stress).text
                    st.markdown("---")
                    st.markdown(risposta_stress)
                except Exception as e: st.error(f"Errore: {e}")
        else: st.error("Inserisci la GEMINI_API_KEY nei secrets.")

# ----------------- SCHEDA 5 (AI Chatbot) -----------------
with tab5:
    st.header("🤖 Quant AI Assistant")
    if "GEMINI_API_KEY" in st.secrets:
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            modelli_disponibili = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target_model = next((m for m in modelli_disponibili if "flash" in m.lower() or "pro" in m.lower()), modelli_disponibili[0])
            model = genai.GenerativeModel(target_model)
            
            if "chat_history" not in st.session_state: st.session_state.chat_history = []
            for m in st.session_state.chat_history: st.chat_message("user" if m["role"]=="user" else "assistant").markdown(m["content"])
            
            if prompt := st.chat_input("Chiedimi un'analisi..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                st.chat_message("user").markdown(prompt)
                with st.spinner("Analisi AI in corso..."):
                    response = model.generate_content(f"{ai_context}\n\nDomanda: {prompt}")
                    st.chat_message("assistant").markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
        except: st.error("Errore API.")

# ----------------- SCHEDA 6 (Academy) -----------------
with tab6:
    st.header("📚 Macro Academy")
    with st.expander("🌍 1. Macroeconomia & Banche Centrali"): st.markdown("**Che cos'è la Macroeconomia?**\nStudio del comportamento dell'economia. La Banca Centrale governa tutto coi tassi.\n\n**Regola base:** Inflazione alta = Tassi alti = Azioni scendono.")
    with st.expander("📈 2. Rotazione Settoriale"): st.markdown("I capitali si spostano in base al ciclo:\n* **Ciclici (Tech, Lusso):** Economia in crescita.\n* **Difensivi (Salute, Utilities):** Recessioni.")
    with st.expander("🏛️ 3. Curva dei Rendimenti"): st.markdown("Se i tassi a breve termine superano quelli a lungo termine, c'è panico nel presente. Segnala quasi sempre una **Recessione** in arrivo.")
    with st.expander("💱 4. Dollaro e Oro"): st.markdown("Il **Dollaro (DXY)** è il bene rifugio. Se c'è panico, sale e le Azioni scendono. L'**Oro** protegge da svalutazione e disastri geopolitici.")
    with st.expander("👁️ 5. Smart Money e Divergenze"): st.markdown("I piccoli investitori (retail) guardano i prezzi. I grandi fondi (Smart Money) guardano il mercato del Credito (Obbligazioni Corporate / HYG). Se le azioni salgono ma l'HYG scende, significa che le banche stanno segretamente vendendo rischio.")
