import streamlit as st
import pandas as pd
import google.generativeai as genai
from io import BytesIO

# Importa i motori dal file engine.py
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Macro Dashboard Pro", page_icon="📊", layout="wide")

# Titolo principale del Terminale
st.title("📊 Global Macro & AI Terminal")
st.subheader("Centro di Comando e Overview Strategica")

# --- SIDEBAR: CONTROLLI GLOBALI E STRUMENTI AI ---
st.sidebar.header("⚙️ Parametri Globali")
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

# --- SINCRONIZZAZIONE DATI ---
with st.spinner("🔄 Caricamento dati in corso..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        hash_status, _ = get_onchain_metrics()
        tension_index, _, _ = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        supabase_client = init_supabase()
    except Exception as e:
        st.error(f"Errore di connessione: {e}")
        st.stop()

# --- SMART ALERTS (PRIORITÀ MASSIMA NELLA HOME) ---
alerts = check_smart_alerts(df, live_prices, tension_index, hash_status)
if alerts:
    st.markdown("### 🚨 Segnali Operativi Urgenti")
    for alert in alerts:
        if "BUY SIGNAL" in alert or "🚀" in alert or "🟢" in alert:
            st.success(f"**{alert}**")
        else:
            st.error(f"**{alert}**")
    st.markdown("---")

# --- STATO GENERALE DEL MERCATO ---
fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)

c1, c2 = st.columns([2, 1])

with c1:
    st.markdown(f"### 🚦 Fase Macro Attuale: **{fase_attuale}**")
    
    # Metriche Chiave
    m1, m2, m3, m4 = st.columns(4)
    sp500_live = live_prices.get('^GSPC', current.get('S&P 500', 0))
    vix_live = live_prices.get('^VIX', current.get('VIX', 0))
    liq_delta = current.get('Liquidity_Delta_30d', 0)
    
    m1.metric("S&P 500 (Live)", f"{sp500_live:,.2f}", delta=f"Z: {current.get('Z_S&P 500', 0):.2f}")
    m2.metric("Liquidità FED", f"${current.get('Fed_Liquidity_T', 0):.2f}T", delta=f"{liq_delta:.2f}T")
    m3.metric("Shiller CAPE", f"{current.get('CAPE', 0):.2f}")
    m4.metric("VIX (Fear)", f"{vix_live:.2f}")

with c2:
    with st.expander("📚 Cruscotto Rapido", expanded=True):
        st.markdown("""
        * **Verde:** Mercato in espansione.
        * **Giallo:** Incertezza / Rotazione.
        * **Rosso:** Rischio sistemico elevato.
        """)

st.info("👈 Usa il menu a sinistra per approfondire le analisi nelle sezioni dedicate (Macro, Crypto, Risk Manager).")

# --- SIDEBAR TOOLS: REPORT AI & TELEGRAM ---
st.sidebar.markdown("---")
st.sidebar.subheader("🗞️ Morning Briefing AI")
ai_context = f"Fase: {fase_attuale}, S&P500 Z: {current.get('Z_S&P 500', 0):.2f}, Liquidity Delta: {liq_delta:.2f}T, Tension Index: {tension_index}/100, On-Chain: {hash_status}."

if "briefing_home" not in st.session_state: st.session_state.briefing_home = ""

if st.sidebar.button("🤖 Genera Report Istantaneo", use_container_width=True):
    if "GEMINI_API_KEY" in st.secrets:
        with st.sidebar.status("L'AI sta analizzando i mercati..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model_name = next((m.name for m in genai.list_models() if "flash" in m.name.lower()), "gemini-1.5-flash")
            st.session_state.briefing_home = genai.GenerativeModel(model_name).generate_content(f"Agisci come un analista quantitativo. Riassumi lo stato del mercato basandoti su: {ai_context}. Sii breve e incisivo.").text
    else: st.sidebar.error("Chiave AI mancante.")

if st.session_state.briefing_home:
    with st.sidebar.expander("📄 Visualizza Report", expanded=True):
        st.markdown(st.session_state.briefing_home)

st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Bot Telegram")
bot_url = get_telegram_link()
st.sidebar.markdown(f'<a href="{bot_url}" target="_blank"><button style="width:100%; border-radius:5px; background-color:#24A1DE; color:white; border:none; padding:10px; font-weight:bold; cursor:pointer;">🚀 Collega Telegram</button></a>', unsafe_allow_html=True)

tg_id = st.sidebar.text_input("Inserisci ID per sincronizzare:")
if st.sidebar.button("💾 Sincronizza ID", use_container_width=True):
    if tg_id and supabase_client:
        try:
            supabase_client.table("telegram_users").insert({"chat_id": str(tg_id)}).execute()
            st.sidebar.success("Sincronizzato!")
        except: st.sidebar.info("ID già presente.")
