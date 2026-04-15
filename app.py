import streamlit as st
import pandas as pd
import google.generativeai as genai
from io import BytesIO

# Importa i motori
from engine import *

# --- CONFIGURAZIONE PAGINA HOME ---
st.set_page_config(page_title="Macro Dashboard Pro", page_icon="📊", layout="wide")
st.title("📊 Terminale Centrale: Overview")

with st.expander("📚 Cruscotto Rapido (Come leggere i dati)"):
    st.markdown("""
    * **Benvenuto nel tuo Terminale Quantitativo.**
    * Usa il menu laterale a sinistra per navigare tra le sezioni specifiche (Macro, Crypto, Risk Management, ecc.).
    * Qui nella Home troverai i segnali di allarme in tempo reale e il tuo assistente per generare i report.
    """)

# --- CARICAMENTO DATI GLOBALI ---
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

with st.spinner("📊 Sincronizzazione Dati Live e Motori FED..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        hash_status, df_hash = get_onchain_metrics()
        tension_index, top_news, region_scores = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        supabase_client = init_supabase()
    except Exception as e:
        st.error(f"Errore di connessione ai fornitori dati: {e}")
        st.stop()

if current.empty:
    st.error("Dati storici non disponibili. Riprova tra qualche minuto.")
    st.stop()

# --- SMART ALERTS (HOME PAGE) ---
alerts = check_smart_alerts(df, live_prices, tension_index, hash_status)
if alerts:
    st.markdown("### 🚨 Avvisi Operativi in Tempo Reale")
    for alert in alerts:
        if "BUY SIGNAL" in alert or "🚀" in alert or "🟢" in alert:
            st.success(f"**{alert}**")
        else:
            st.error(f"**{alert}**")
    st.markdown("---")

# --- PANORAMICA MACRO ---
fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)
st.header("🚦 Semaforo Macro Intelligente")
if "1." in fase_attuale: st.error(f"🚨 **FASE DI MERCATO: {fase_attuale}**")
elif "2." in fase_attuale: st.warning(f"⚖️ **FASE DI MERCATO: {fase_attuale}**")
else: st.success(f"🚀 **FASE DI MERCATO: {fase_attuale}**")

col_live1, col_live2, col_live3, col_live4 = st.columns(4)
sp500_live = live_prices.get('^GSPC', current.get('S&P 500', 0))
vix_live = live_prices.get('^VIX', current.get('VIX', 0))
liq_delta = current.get('Liquidity_Delta_30d', 0)
cape_val = current.get('CAPE', 0)

col_live1.metric("S&P 500 (Live)", f"{sp500_live:,.2f}", delta=f"Z-Score: {current.get('Z_S&P 500', 0):.2f}")
col_live2.metric("Liquidità FED Netta", f"${current.get('Fed_Liquidity_T', 0):.2f}T", delta=f"{'+' if liq_delta > 0 else ''}{liq_delta:.2f}T (30g)", delta_color="normal")
col_live3.metric("Shiller P/E (CAPE)", f"{cape_val:.2f}", delta="> 30 Rischio Bolla", delta_color="inverse" if cape_val > 30 else "normal")
col_live4.metric("VIX Index (Paura)", f"{vix_live:.2f}", delta="Volatilità", delta_color="off")

# --- SIDEBAR: STRUMENTI PRO ---
st.sidebar.markdown("---")
ai_context = f"Fase Macro: {fase_attuale}, S&P500 Z-Score: {current.get('Z_S&P 500', 0):.2f}, Shiller CAPE: {current.get('CAPE', 0):.2f}, Liquidità FED Delta 30g: {current.get('Liquidity_Delta_30d', 0):.2f}T, Oro Z-Score: {current.get('Z_Oro', 0):.2f}, BTC Mayer: {current.get('Mayer_BTC', 0):.2f}, On-Chain BTC: {hash_status}."

st.sidebar.subheader("🗞️ Generatore Report AI")
if "morning_brief" not in st.session_state: st.session_state.morning_brief = ""

if st.sidebar.button("🤖 Genera Morning Briefing", use_container_width=True):
    if "GEMINI_API_KEY" in st.secrets:
        with st.sidebar.status("Elaborazione istituzionale in corso..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            mod = next((m.name for m in genai.list_models() if "flash" in m.name.lower() or "pro" in m.name.lower()), "gemini-1.5-flash")
            st.session_state.morning_brief = genai.GenerativeModel(mod).generate_content(f"Sei il Chief Investment Officer. Scrivi un report strategico mattutino basato su: {ai_context}. Usa il Markdown.").text
    else: st.sidebar.error("Chiave GEMINI mancante nei Secrets.")

if st.session_state.morning_brief:
    with st.sidebar.expander("📄 Leggi il Report", expanded=True):
        st.markdown(st.session_state.morning_brief)

st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Automazione Notifiche")
bot_link = get_telegram_link()

st.sidebar.markdown(f"""
<a href="{bot_link}" target="_blank" style="text-decoration:none;">
    <button style="width:100%; border-radius:5px; background-color:#24A1DE; color:white; border:none; padding:10px; cursor:pointer; font-weight:bold;">
        🚀 Attiva Bot Telegram
    </button>
</a>
""", unsafe_allow_html=True)

tg_user_id = st.sidebar.text_input("ID Telegram (se manuale):")
if st.sidebar.button("💾 Salva ID nel Database", use_container_width=True):
    if tg_user_id and supabase_client:
        try:
            supabase_client.table("telegram_users").insert({"chat_id": str(tg_user_id)}).execute()
            st.sidebar.success("✅ Sincronizzazione Database completata!")
        except Exception as e:
            if "duplicate key" in str(e).lower(): st.sidebar.info("✅ ID già presente nel sistema.")
            else: st.sidebar.error("Errore DB Supabase.")
