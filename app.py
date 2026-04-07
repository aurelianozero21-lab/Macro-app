import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
from io import BytesIO
from datetime import datetime

# Importiamo i calcoli e il database dal motore
from engine import *

st.set_page_config(page_title="Macro Dashboard Pro", layout="wide")
st.title("📊 Global Macro, Crypto & AI Assistant")

with st.expander("📚 Legenda e Glossario Rapido"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend (> 0) o in declino (< 0). >2 Ipercomprato, <-2 Ipervenduto.
    * **Curva Rendimenti:** Se Invertita (< 0) segnala panico nel breve e possibile recessione.
    * **Mayer Multiple:** BTC / media 200gg. < 1.0 = Accumulo (Sconto). > 2.4 = Bolla.
    * **Smart Money (HYG):** Se le azioni salgono ma l'HYG scende, le banche vendono rischio di nascosto.
    """)

# --- INIZIALIZZAZIONE DATI ---
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)
with st.spinner("📊 Sincronizzazione Dati Live..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        df_etfs = get_etf_screener()
        df_crypto = get_crypto_screener()
        fgi_val, fgi_class = get_crypto_fgi()
        tension_index, top_news, region_scores = analyze_geopolitics()
        current = df.iloc[-1]
        supabase_client = init_supabase()
    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        st.stop()

fase_attuale = calcola_fase_avanzata(current['YieldCurve'], current['Z_S&P 500'], tension_index)
ai_context = f"Fase: {fase_attuale}, S&P500 Z:{current['Z_S&P 500']:.2f}, Oro Z:{current['Z_Oro']:.2f}, Geopolitica:{tension_index}, BTC Mayer:{current['Mayer_BTC']:.2f}, FGI: {fgi_val}."

# --- SIDEBAR: EXPORT & AI ---
st.sidebar.markdown("---")
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=True, sheet_name='Data')
    writer.close()
    return output.getvalue()
st.sidebar.download_button("📥 Scarica Dati (Excel)", data=to_excel(df), file_name="macro_data.xlsx", mime="application/vnd.ms-excel")

st.sidebar.markdown("---")
st.sidebar.subheader("🗞️ Morning Briefing AI")
if "morning_brief" not in st.session_state: st.session_state.morning_brief = ""
if st.sidebar.button("🤖 Genera Report"):
    if "GEMINI_API_KEY" in st.secrets:
        with st.sidebar.status("✍️ Stesura report in corso..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            modelli = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            mod = next((m for m in modelli if "flash" in m.lower() or "pro" in m.lower()), modelli[0])
            st.session_state.morning_brief = genai.GenerativeModel(mod).generate_content(f"Sei un CIO istituzionale. Scrivi un Morning Brief sintetico basato su: {ai_context}. Markdown.").text
    else: st.sidebar.warning("Manca API Key.")

if st.session_state.morning_brief:
    with st.sidebar.expander("📄 Visualizza", expanded=True):
        st.markdown(st.session_state.morning_brief)
        st.download_button("💾 Scarica (.md)", data=st.session_state.morning_brief, file_name=f"Brief_{datetime.now().strftime('%Y%m%d')}.md")

# --- SIDEBAR: TELEGRAM ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Notifiche Telegram")
query_params = st.query_params
url_id = query_params.get("id", "")
bot_link = get_telegram_link()

st.sidebar.markdown(f"""
<a href="{bot_link}" target="_blank">
    <button style="width:100%; border-radius:5px; background-color:#24A1DE; color:white; border:none; padding:10px; cursor:pointer;">
        🚀 Apri Telegram e Attiva
    </button>
</a>
""", unsafe_allow_html=True)

tg_user_id = st.sidebar.text_input("Oppure incolla il tuo ID:", value=url_id)
if st.sidebar.button("💾 Salva Iscrizione"):
    if tg_user_id and supabase_client:
        try:
            supabase_client.table("telegram_users").insert({"chat_id": str(tg_user_id)}).execute()
            st.sidebar.success("✅ Iscritto al Database!")
            st.query_params.clear()
        except Exception as e:
            if "duplicate key" in str(e).lower(): st.sidebar.success("✅ Sei già iscritto!")
            else: st.sidebar.error("Errore di connessione al DB.")

# --- SCHEDE PRINCIPALI ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏛️ Macro", "⚡ Crypto", "🌍 Geopolitica", "🔥 Stress Test", "🤖 Chatbot", "📚 Academy"])

# --- 1. MACRO ---
with tab1:
    st.header("🚦 Semaforo Macro Intelligente")
    if "1." in fase_attuale: st.error(f"🚨 **FASE ATTUALE: {fase_attuale}**")
    elif "2." in fase_attuale: st.warning(f"⚖️ **FASE ATTUALE: {fase_attuale}**")
    else: st.success(f"🚀 **FASE ATTUALE: {fase_attuale}**")
    
    col_live1, col_live2 = st.columns(2)
    sp500_live = live_prices.get('^GSPC', current['S&P 500'])
    vix_live = live_prices.get('^VIX', current['VIX'])
    col_live1.metric("S&P 500 (Live)", f"{sp500_live:,.2f}", delta=f"Z-Score: {current['Z_S&P 500']:.2f}")
    col_live2.metric("VIX Index (Live)", f"{vix_live:.2f}", delta="Volatilità Attuale", delta_color="off")
    
    st.markdown("---")
    st.header("👁️ Smart Money Radar")
    col_sm1, col_sm2 = st.columns(2)
    with col_sm1:
        st.subheader("🏦 Rischio di Credito (HYG)")
        if current['Z_S&P 500'] > 0 and current['Z_High Yield'] < 0: st.error("⚠️ **DIVERGENZA RIBASSISTA**\nLe banche stanno vendendo rischio.")
        elif current['Z_S&P 500'] < 0 and current['Z_High Yield'] > 0: st.success("🟢 **DIVERGENZA RIALZISTA**\nLo Smart Money sta comprando.")
        else: st.info("⚖️ **CONVERGENZA**\nAzionario e mercato del credito allineati.")
    with col_sm2:
        st.subheader("📉 Indice della Paura (VIX)")
        if vix_live < 15: st.warning("😴 **Compiacenza Estrema**\nMercato tranquillo, rischio shock.")
        elif vix_live > 25: st.error("😱 **Panico e Volatilità**\nMercato sotto stress. Opportunità sui minimi.")
        else: st.success("✅ **Normale**\nNessuno stress sistemico.")

    st.markdown("---")
    st.header("🎯 Strategia Temporale")
    col_st, col_mt, col_lt = st.columns(3)
    with col_st: 
        st.subheader("⏱️ Breve (1-3 Mesi)")
        if tension_index >= 60: st.error("🛡️ **Focus:** Geopolitica e Difesa (Oro, Utilities)")
        elif "1." in fase_attuale: st.warning("🧱 **Focus:** Protezione Capitale (Cash, Bond a breve)")
        else: st.success("🔥 **Focus:** Momentum Azionario (Tech, Finanza)")
    with col_mt: 
        st.subheader("📅 Medio (6-12 Mesi)")
        if "1." in fase_attuale or "2." in fase_attuale: st.warning("📉 **Focus:** Anticipare Taglio Tassi (Obbligazioni a lungo termine)")
        else: st.success("🏭 **Focus:** Rotazione Ciclica ed Espansione Azionaria")
    with col_lt: 
        st.subheader("🔭 Lungo (1-3 Anni)")
        st.info("🌐 **Mega-Trend:** Intelligenza Artificiale, Transizione Energetica (Rame/Uranio), Cybersecurity.")

    if not df_etfs.empty:
        st.markdown("---")
        st.header("🗺️ Mappa Settoriale e Segnali ETF")
        col_g1, col_g2 = st.columns(2)
        with col_g1: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Geografia'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Geografie (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)
        with col_g2: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Settore'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Settori USA (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)
        st.dataframe(df_etfs[['Asset', 'Categoria', 'Prezzo ($)', 'Perf. 1 Mese (%)', 'Segnale Operativo']].sort_values(by='Perf. 1 Mese (%)', ascending=False), use_container_width=True, hide_index=True)

# --- 2. CRYPTO ---
with tab2:
    st.header("⚡ Crypto Cycle")
    mayer_btc = current['Mayer_BTC']
    col_pre1, col_pre2 = st.columns(2)
    with col_pre1:
        if mayer_btc < 1.0: st.success("🔋 **Fase: ACCUMULO (Sconto)**")
        elif mayer_btc < 2.0: st.warning("📈 **Fase: BULL MARKET**")
        else: st.error("💥 **Fase: BOLLA SPECULATIVA**")
    with col_pre2:
        st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=fgi_val, title={'text': f"Fear & Greed: {fgi_class}"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 45], 'color': "#e57373"}, {'range': [55, 100], 'color': "#81c784"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    btc_live = live_prices.get('BTC-USD', current['Bitcoin'])
    c1.metric("Prezzo BTC (Live)", f"${btc_live:,.0f}")
    c2.metric("Mayer Multiple", f"{mayer_btc:.2f}")
    c3.metric("RSI (14 gg)", f"{current['RSI_BTC']:.0f}")
    c4.metric("Distanza ATH", f"{current['BTC_Drawdown']:.1f}%")
    if not df_crypto.empty: st.plotly_chart(px.bar(df_crypto, x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Altcoin Rotation (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)

# --- 3. GEOPOLITICA ---
with tab3:
    st.header("🌍 Geopolitical Intelligence")
    col_g1, col_g2, col_g3 = st.columns([1.5, 1, 1.2])
    with col_g1: st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=tension_index, title={'text': "Tensione Globale"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"}, {'range': [60, 100], 'color': "#e57373"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)
    with col_g2:
        st.subheader("🗺️ Hotspots")
        for region, count in region_scores.items(): st.metric(region, f"{count} news", delta="🔥 Caldo" if count >= 2 else "Calmo", delta_color="inverse" if count >= 2 else "normal")
    with col_g3:
        st.subheader("🛢️ Beni Rifugio / Energia")
        gold_live = live_prices.get('GC=F', current['Oro'])
        oil_live = live_prices.get('CL=F', 0.0)
        st.metric("Oro (Live)", f"${gold_live:,.1f}", delta=f"Z-Score: {current['Z_Oro']:.2f}", delta_color="inverse" if current['Z_Oro'] > 1 else "normal")
        st.metric("Petrolio WTI (Live)", f"${oil_live:,.2f}", delta="Barile", delta_color="off")

    if top_news:
        st.markdown("---")
        st.subheader("📰 Ultime Notizie Rilevate")
        for item in top_news: st.markdown(f"- **[{'🔴 Tension' if item['score'] > 0 else '🟢 Peace'}]** [{item['titolo']}]({item['link']})")

# --- 4. STRESS TEST ---
with tab4:
    st.header("🔥 Stress Test Portafoglio")
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1: alloc_azioni = st.number_input("Azioni (%)", 0, 100, 50)
    with col_p2: alloc_obbligazioni = st.number_input("Bonds (%)", 0, 100, 20)
    with col_p3: alloc_crypto = st.number_input("Crypto (%)", 0, 100, 10)
    with col_p4: alloc_difesa = st.number_input("Oro/Cash (%)", 0, 100, 20)
    
    if st.button("🚀 Esegui Analisi AI", use_container_width=True):
        if "GEMINI_API_KEY" in st.secrets:
            with st.spinner("Valutazione in corso..."):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                mod = next((m.name for m in genai.list_models() if "flash" in m.name.lower() or "pro" in m.name.lower()), "gemini-1.5-flash")
                st.markdown("---")
                st.markdown(genai.GenerativeModel(mod).generate_content(f"Risk Manager: Asset={alloc_azioni}/{alloc_obbligazioni}/{alloc_crypto}/{alloc_difesa}. Macro={ai_context}. In Markdown.").text)
        else: st.error("Manca GEMINI_API_KEY.")

# --- 5. CHATBOT ---
with tab5:
    st.header("🤖 Quant AI Assistant")
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        mod = next((m.name for m in genai.list_models() if "flash" in m.name.lower()), "gemini-1.5-flash")
        
        if "chat_history" not in st.session_state: st.session_state.chat_history = []
        for m in st.session_state.chat_history: st.chat_message(m["role"]).markdown(m["content"])
        
        if prompt := st.chat_input("Chiedimi un'analisi..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.chat_message("user").markdown(prompt)
            res = genai.GenerativeModel(mod).generate_content(f"Contesto: {ai_context}\n\nDomanda: {prompt}").text
            st.chat_message("assistant").markdown(res)
            st.session_state.chat_history.append({"role": "assistant", "content": res})

# --- 6. ACADEMY ---
with tab6:
    st.header("📚 Macro Academy: Masterclass per Investitori")
    st.write("Comprendi i concetti quantitativi alla base di questa dashboard per prendere decisioni consapevoli.")
    
    with st.expander("📊 1. Lo Z-Score (La Misura dell'Eccesso)"): 
        st.markdown("""
        Lo **Z-Score** è un indicatore statistico. Ci dice di quante "deviazioni standard" il prezzo attuale si è allontanato dalla sua media storica (nel nostro caso, a 90 giorni).
        * **Z-Score vicino a 0:** L'asset è al suo prezzo "giusto" o in linea con il trend.
        * **Z-Score > 2:** L'asset è salito troppo e troppo in fretta (Ipercomprato). Alto rischio di crollo.
        * **Z-Score < -2:** L'asset è stato venduto eccessivamente per panico (Ipervenduto). Possibile occasione d'acquisto.
        """)
        
    with st.expander("🏛️ 2. La Curva dei Rendimenti (L'Oracolo delle Recessioni)"): 
        st.markdown("""
        Misura la differenza di rendimento tra i Titoli di Stato USA a 10 anni e quelli a 2 anni (T10Y2Y).
        * **Curva Normale (> 0):** I titoli a lungo termine pagano di più. Economia sana e in espansione.
        * **Curva Invertita (< 0):** Il mercato ha così tanta paura del presente che i titoli a 2 anni pagano più di quelli a 10 anni. Storicamente, ha anticipato il 100% delle recessioni moderne.
        """)
        
    with st.expander("👁️ 3. Smart Money Divergence (HYG vs S&P 500)"): 
        st.markdown("""
        I piccoli investitori guardano solo i prezzi delle azioni. I grandi fondi istituzionali ("Smart Money") guardano il **Mercato del Credito** e le obbligazioni spazzatura (High Yield - Ticker: HYG).
        * **Divergenza Ribassista (Pericolo):** L'S&P 500 sale, ma l'HYG scende. Significa che il "Retail" sta comprando azioni in preda all'euforia, mentre le Banche stanno segretamente vendendo asset rischiosi. Un crollo è imminente.
        * **Divergenza Rialzista (Opportunità):** Le azioni scendono per il panico, ma l'HYG sale. I grandi fondi stanno già ricomprando in saldo.
        """)
        
    with st.expander("₿ 4. Il Mayer Multiple (Il Ciclo Bitcoin)"): 
        st.markdown("""
        Creato da Trace Mayer, si calcola dividendo il prezzo del Bitcoin per la sua Media Mobile a 200 giorni. È il miglior indicatore per capire in che fase del ciclo crypto ci troviamo.
        * **< 1.0 (Accumulo):** Bitcoin costa meno della sua media storica. È la fase in cui comprare genera i massimi rendimenti a lungo termine.
        * **1.0 - 2.0 (Bull Market):** Trend sano e rialzista. Mantenere le posizioni.
        * **> 2.4 (Bolla):** Euforia totale. Il prezzo è insostenibile ed è matematicamente il momento di prendere profitti prima del "Bear Market".
        """)

    with st.expander("📈 5. Rotazione Settoriale (Dove va il denaro)"): 
        st.markdown("""
        Il mercato azionario non si muove tutto insieme. I capitali "ruotano" da un settore all'altro in base a cosa fa la Banca Centrale:
        * **Economia si riprende (Tassi bassi):** Denaro va su Tech (XLK), Finanza (XLF) e Industriali (XLI).
        * **Inflazione alta (Materie prime salgono):** Denaro va su Energia (XLE) e Oro.
        * **Recessione in arrivo (Panico):** Denaro fugge verso porti sicuri come Sanità (XLV), Utilities (XLU) e Cash.
        """)
