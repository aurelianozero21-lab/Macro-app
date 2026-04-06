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

# Gestione sicura per l'importazione di Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

st.set_page_config(page_title="Macro Dashboard Pro", layout="wide")
st.title("📊 Global Macro, Crypto & AI Assistant")

with st.expander("📚 Legenda e Glossario Rapido"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo BTC / media 200gg. < 1.0 = Accumulo. > 2.4 = Bolla.
    * **Smart Money (HYG):** Se scende mentre la borsa sale, i grandi capitali fuggono dal rischio.
    """)

# --- INIZIALIZZAZIONE DATABASE ---
def init_supabase():
    if SUPABASE_AVAILABLE and "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    return None

supabase_client = init_supabase()

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
                prezzo, sma_50, sma_200 = hist['Close'].iloc[-1], hist['Close'].tail(50).mean(), hist['Close'].mean() 
                perf_1m = ((prezzo / hist['Close'].iloc[-21]) - 1) * 100
                segnale = "🟢 Compra" if prezzo > sma_50 and sma_50 > sma_200 else "🟡 Accumula" if prezzo > sma_50 else "🔴 Evita"
                tipo = 'Geografia' if nome in ['USA (SPY)', 'Europa (VGK)', 'Emergenti (EEM)', 'Giappone (EWJ)'] else 'Settore'
                dati.append({'Categoria': tipo, 'Asset': nome, 'Prezzo ($)': round(prezzo, 2), 'Perf. 1 Mese (%)': round(perf_1m, 2), 'Segnale Operativo': segnale})
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
with st.spinner("📊 Sincronizzazione Mercati Globale..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        df_etfs = get_etf_screener()
        fgi_val, fgi_class = get_crypto_fgi()
        tension_index, top_news, region_scores = analyze_geopolitics()
        current = df.iloc[-1]
    except Exception as e:
        st.error(f"Errore: {e}"); st.stop()

def calcola_fase_avanzata(yc, z_sp500, tension):
    if yc < 0 or tension >= 65: return '1. Allarme Rosso (Risk-Off)'
    elif yc > 0 and (z_sp500 < 0 or tension >= 50): return '2. Incertezza / Accumulo Difensivo'
    else: return '3. Espansione (Risk-On)'

fase_attuale = calcola_fase_avanzata(current['YieldCurve'], current['Z_S&P 500'], tension_index)
ai_context = f"Fase: {fase_attuale}, S&P500 Z:{current['Z_S&P 500']:.2f}, Oro Z:{current['Z_Oro']:.2f}, Geopolitica:{tension_index}, BTC Mayer:{current['Mayer_BTC']:.2f}, FGI: {fgi_val}."

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
    with st.sidebar.expander("📄 Visualizza", expanded=True):
        st.markdown(st.session_state.morning_brief)
        st.download_button("💾 Scarica (.md)", data=st.session_state.morning_brief, file_name=f"Brief_{datetime.now().strftime('%Y%m%d')}.md")

# --- NUOVO MODULO SIDEBAR: ABBONAMENTO SAAS CON SUPABASE ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Abbonamento Strategia Daily")

with st.sidebar.expander("📲 Come attivare (Gratis)"):
    bot_url = st.secrets.get("TG_BOT_URL", "https://t.me/Inserisci_Qui_Il_Tuo_Bot")
    st.markdown(f"1. Apri il [Bot 👉 QUI]({bot_url}) e premi **Avvia**.")
    st.markdown("2. Prendi il tuo ID [👉 QUI](https://t.me/getmyid_bot).")
    
tg_user_id = st.sidebar.text_input("3. Incolla il tuo ID per iscriverti:")

if st.sidebar.button("✅ Iscrivimi per sempre", use_container_width=True):
    if tg_user_id:
        if supabase_client:
            try:
                # Salva l'ID utente nel database Supabase
                response = supabase_client.table("telegram_users").insert({"chat_id": str(tg_user_id)}).execute()
                st.sidebar.success(f"🎉 Registrazione salvata nel Database! ID: {tg_user_id}")
                
                # Invia un messaggio di benvenuto automatico su Telegram
                if "TG_TOKEN" in st.secrets:
                    url = f"https://api.telegram.org/bot{st.secrets['TG_TOKEN']}/sendMessage"
                    msg = f"✅ **Iscrizione Confermata!**\n\nBenvenuto a bordo. Il tuo ID `{tg_user_id}` è stato salvato nel database. Riceverai qui la tua strategia quantitativa automatica."
                    requests.post(url, json={"chat_id": tg_user_id, "text": msg, "parse_mode": "Markdown"})
            except Exception as e:
                # Se l'utente è già nel database (evita duplicati se hai impostato l'ID come Primary Key)
                if "duplicate key value" in str(e):
                    st.sidebar.success("Sei già iscritto al servizio! Riceverai i prossimi aggiornamenti.")
                else:
                    st.sidebar.error(f"Errore durante il salvataggio nel DB: {e}")
        else:
            st.sidebar.error("⚠️ Database non configurato. Inserisci SUPABASE_URL e SUPABASE_KEY nei secrets.")
    else:
        st.sidebar.warning("Inserisci il tuo ID Telegram.")

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
    col_sm1, col_sm2 = st.columns(2)
    with col_sm1:
        st.subheader("🏦 Rischio di Credito (HYG)")
        if current['Z_S&P 500'] > 0 and current['Z_High Yield'] < 0: st.error("⚠️ **DIVERGENZA RIBASSISTA (WARNING)**")
        elif current['Z_S&P 500'] < 0 and current['Z_High Yield'] > 0: st.success("🟢 **DIVERGENZA RIALZISTA**")
        else: st.info("⚖️ **CONVERGENZA (Trend Sano)**")
    with col_sm2:
        st.subheader("📉 Indice della Paura (VIX)")
        if current['VIX'] < 15: st.warning(f"😴 **Compiacenza Estrema ({current['VIX']:.1f})**")
        elif current['VIX'] > 25: st.error(f"😱 **Panico e Alta Volatilità ({current['VIX']:.1f})**")
        else: st.success(f"✅ **Volatilità Normale ({current['VIX']:.1f})**")

    st.markdown("---")
    col_st, col_mt, col_lt = st.columns(3)
    with col_st: st.subheader("⏱️ 1-3 Mesi"); st.write(f"Focus: {'Geopolitica' if tension_index >= 60 else 'Protezione' if '1.' in fase_attuale else 'Momentum'}")
    with col_mt: st.subheader("📅 6-12 Mesi"); st.write(f"Focus: {'Taglio Tassi' if '1.' in fase_attuale or '2.' in fase_attuale else 'Espansione'}")
    with col_lt: st.subheader("🔭 1-3 Anni"); st.info("Mega-Trend: AI, Energy, Biotech")

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

# ----------------- SCHEDA 3 (Geopolitica) -----------------
with tab3:
    st.header("🌍 Geopolitical Intelligence")
    col_g1, col_g2, col_g3 = st.columns([1.5, 1, 1])
    with col_g1: st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=tension_index, title={'text': "Tensione Globale"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [60, 100], 'color': "#e57373"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)
    with col_g2:
        st.subheader("🗺️ Hotspots")
        for region, count in region_scores.items(): st.metric(region, f"{count} news", delta="🔥 Caldo" if count >= 2 else "Calmo", delta_color="inverse" if count >= 2 else "normal")
    with col_g3: st.subheader("🛢️ Reality Check"); st.metric("Trend Oro (Z-Score)", f"{current['Z_Oro']:.2f}", delta="Risk-Off" if current['Z_Oro'] > 1 else "Neutro")

    if top_news:
        for item in top_news: st.markdown(f"- **[{'🔴 Tension' if item['score'] > 0 else '🟢 Peace'}]** [{item['titolo']}]({item['link']})")

# ----------------- SCHEDA 4 (🔥 STRESS TEST) -----------------
with tab4:
    st.header("🔥 Stress Test Portafoglio")
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1: a_az = st.number_input("Azioni (%)", 0, 100, 50)
    with col_p2: a_bo = st.number_input("Obbligazioni (%)", 0, 100, 20)
    with col_p3: a_cr = st.number_input("Cripto (%)", 0, 100, 10)
    with col_p4: a_di = st.number_input("Oro/Cash (%)", 0, 100, 20)
    
    if st.button("🚀 Esegui Stress Test AI"):
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Risk Manager: Portafoglio {a_az}/{a_bo}/{a_cr}/{a_di}. Macro: {ai_context}. Report Markdown."
            st.markdown(model.generate_content(prompt).text)

# ----------------- SCHEDA 5 (AI Chatbot) -----------------
with tab5:
    st.header("🤖 AI Chatbot")
    if "GEMINI_API_KEY" in st.secrets:
        if "chat_history" not in st.session_state: st.session_state.chat_history = []
        for m in st.session_state.chat_history: st.chat_message(m["role"]).markdown(m["content"])
        if pr := st.chat_input("Chiedimi..."):
            st.session_state.chat_history.append({"role": "user", "content": pr})
            st.chat_message("user").markdown(pr)
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            res = genai.GenerativeModel('gemini-1.5-flash').generate_content(f"{ai_context}\n\nDomanda: {pr}").text
            st.chat_message("assistant").markdown(res)
            st.session_state.chat_history.append({"role": "assistant", "content": res})

# ----------------- SCHEDA 6 (Academy) -----------------
with tab6:
    st.header("📚 Academy")
    with st.expander("🌍 1. Macroeconomia"): st.write("Tassi alti = Azioni scendono. Tassi bassi = Azioni salgono.")
    with st.expander("📈 2. Rotazione"): st.write("Ciclici per crescita, Difensivi per recessione.")
    with st.expander("🏛️ 3. Curva Rendimenti"): st.write("Se invertita, segnale di recessione imminente.")
    with st.expander("👁️ 5. Smart Money"): st.write("Se l'azionario sale ma il credito (HYG) scende, lo Smart Money sta vendendo.")
