import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
from io import BytesIO
import requests
from datetime import datetime

# Importiamo il motore separato
from engine import *

st.set_page_config(page_title="Macro Dashboard Pro", layout="wide")
st.title("📊 Global Macro, Crypto & AI Assistant")

with st.expander("📚 Legenda e Glossario Rapido"):
    st.markdown("""
    * **Z-Score:** Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva Rendimenti:** Se Invertita (< 0) segnala recessione. 
    * **Mayer Multiple:** Prezzo BTC / media 200gg. < 1.0 = Accumulo. > 2.4 = Bolla.
    * **Smart Money (HYG):** Se scende mentre la borsa sale, i grandi capitali fuggono dal rischio.
    """)

# --- INIZIALIZZAZIONE DATI ---
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)
with st.spinner("📊 Sincronizzazione Dati..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices() # Dati a 1 minuto per i prezzi spot
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

# --- SIDEBAR E MORNING BRIEF ---
st.sidebar.markdown("---")
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=True, sheet_name='Data')
    writer.close()
    return output.getvalue()
st.sidebar.download_button("📥 Scarica Excel", data=to_excel(df), file_name="macro_data.xlsx", mime="application/vnd.ms-excel")

st.sidebar.markdown("---")
st.sidebar.subheader("🗞️ Morning Briefing AI")
if "morning_brief" not in st.session_state: st.session_state.morning_brief = ""
if st.sidebar.button("🤖 Genera Report"):
    if "GEMINI_API_KEY" in st.secrets:
        with st.sidebar.status("✍️ Stesura report..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            modelli = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            mod = next((m for m in modelli if "flash" in m.lower() or "pro" in m.lower()), modelli[0])
            st.session_state.morning_brief = genai.GenerativeModel(mod).generate_content(f"Sei un CIO. Scrivi un Morning Brief basato su: {ai_context}. Markdown.").text
    else: st.sidebar.warning("Manca API Key.")

if st.session_state.morning_brief:
    with st.sidebar.expander("📄 Visualizza", expanded=True):
        st.markdown(st.session_state.morning_brief)
        st.download_button("💾 Scarica (.md)", data=st.session_state.morning_brief, file_name=f"Brief_{datetime.now().strftime('%Y%m%d')}.md")

# --- ABBONAMENTO SMART (1 CLICK) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Iscrizione Rapida")
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

st.sidebar.write("Oppure inserisci manualmente:")
tg_user_id = st.sidebar.text_input("ID Telegram:", value=url_id)

if st.sidebar.button("💾 Salva Iscrizione"):
    if tg_user_id and supabase_client:
        try:
            supabase_client.table("telegram_users").insert({"chat_id": str(tg_user_id)}).execute()
            st.sidebar.success("✅ Iscritto al Database!")
            st.query_params.clear()
        except Exception as e:
            if "duplicate key" in str(e).lower(): st.sidebar.success("✅ Sei già iscritto!")
            else: st.sidebar.error(f"Errore DB: {e}")
            
# --- SCHEDE PRINCIPALI ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏛️ Macro", "⚡ Crypto", "🌍 Geopolitica", "🔥 Stress Test", "🤖 AI Chatbot", "📚 Academy"])

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
        vix_live = live_prices.get('^VIX', current['VIX'])
        if vix_live < 15: st.warning(f"😴 **Compiacenza Estrema ({vix_live:.1f})**")
        elif vix_live > 25: st.error(f"😱 **Panico e Alta Volatilità ({vix_live:.1f})**")
        else: st.success(f"✅ **Volatilità Normale ({vix_live:.1f})**")

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
    btc_live = live_prices.get('BTC-USD', current['Bitcoin'])
    c1.metric("Prezzo BTC (Live)", f"${btc_live:,.0f}")
    c2.metric("Mayer Multiple", f"{mayer_btc:.2f}")
    c3.metric("RSI (14 gg)", f"{current['RSI_BTC']:.0f}")
    c4.metric("Distanza da ATH", f"{current['BTC_Drawdown']:.1f}%")

    if not df_crypto.empty:
        st.plotly_chart(px.bar(df_crypto, x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Altcoin Rotation (1M)").update_layout(coloraxis_showscale=False, height=300), use_container_width=True)

with tab3:
    st.header("🌍 Geopolitical Intelligence")
    col_g1, col_g2, col_g3 = st.columns([1.5, 1, 1])
    with col_g1: st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=tension_index, title={'text': "Tensione Globale"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"}, {'range': [60, 100], 'color': "#e57373"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)
    with col_g2:
        st.subheader("🗺️ Hotspots")
        for region, count in region_scores.items(): st.metric(region, f"{count} news", delta="🔥 Caldo" if count >= 2 else "Calmo", delta_color="inverse" if count >= 2 else "normal")
    with col_g3:
        st.subheader("🛢️ Reality Check")
        gold_live = live_prices.get('GC=F', current['Oro'])
        st.metric("Oro (Live)", f"${gold_live:.1f}", delta=f"Z-Score: {current['Z_Oro']:.2f}")

    st.markdown("---")
    st.subheader("📰 Ultime Notizie Analizzate")
    if top_news:
        for item in top_news: st.markdown(f"- **[{'🔴 Tension' if item['score'] > 0 else '🟢 Peace'}]** [{item['titolo']}]({item['link']})")

with tab4:
    st.header("🔥 Stress Test & Ottimizzazione")
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1: alloc_azioni = st.number_input("Azioni / ETF (%)", 0, 100, 50)
    with col_p2: alloc_obbligazioni = st.number_input("Obbligazioni (%)", 0, 100, 20)
    with col_p3: alloc_crypto = st.number_input("Cripto (%)", 0, 100, 10)
    with col_p4: alloc_difesa = st.number_input("Oro / Cash (%)", 0, 100, 20)
    
    if st.button("🚀 Esegui Stress Test con AI", use_container_width=True):
        if "GEMINI_API_KEY" in st.secrets:
            with st.spinner("Risk Manager AI in analisi..."):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                modelli = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                mod = next((m for m in modelli if "flash" in m.lower() or "pro" in m.lower()), modelli[0])
                prompt = f"Risk Manager: Portafoglio {alloc_azioni}% Azioni, {alloc_obbligazioni}% Bond, {alloc_crypto}% Crypto, {alloc_difesa}% Oro. Macro: {ai_context}. Report Markdown."
                st.markdown("---")
                st.markdown(genai.GenerativeModel(mod).generate_content(prompt).text)
        else: st.error("Manca GEMINI_API_KEY nei secrets.")

with tab5:
    st.header("🤖 Quant AI Assistant")
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        modelli_disponibili = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = next((m for m in modelli_disponibili if "flash" in m.lower() or "pro" in m.lower()), modelli_disponibili[0])
        model = genai.GenerativeModel(target_model)
        
        if "chat_history" not in st.session_state: st.session_state.chat_history = []
        for m in st.session_state.chat_history: st.chat_message("user" if m["role"]=="user" else "assistant").markdown(m["content"])
        
        if prompt := st.chat_input("Chiedimi un'analisi..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.chat_message("user").markdown(prompt)
            with st.spinner("Analisi in corso..."):
                res = model.generate_content(f"{ai_context}\n\nDomanda: {prompt}").text
                st.chat_message("assistant").markdown(res)
                st.session_state.chat_history.append({"role": "assistant", "content": res})

with tab6:
    st.header("📚 Macro Academy")
    with st.expander("🌍 1. Macroeconomia & Banche Centrali"): st.markdown("**Che cos'è la Macroeconomia?**\nStudio del comportamento dell'economia. La Banca Centrale governa tutto coi tassi.\n\n**Regola base:** Inflazione alta = Tassi alti = Azioni scendono.")
    with st.expander("📈 2. Rotazione Settoriale"): st.markdown("I capitali si spostano in base al ciclo:\n* **Ciclici (Tech, Lusso):** Economia in crescita.\n* **Difensivi (Salute, Utilities):** Recessioni.")
    with st.expander("🏛️ 3. Curva dei Rendimenti"): st.markdown("Se i tassi a breve termine superano quelli a lungo termine, c'è panico nel presente. Segnala quasi sempre una **Recessione** in arrivo.")
    with st.expander("💱 4. Dollaro e Oro"): st.markdown("Il **Dollaro (DXY)** è il bene rifugio. Se c'è panico, sale e le Azioni scendono. L'**Oro** protegge da svalutazione e disastri geopolitici.")
    with st.expander("👁️ 5. Smart Money e Divergenze"): st.markdown("I grandi fondi (Smart Money) guardano il Credito (HYG). Se le azioni salgono ma l'HYG scende, le banche stanno vendendo rischio.")
