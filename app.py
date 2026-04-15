import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
from io import BytesIO

# Importa tutta la logica dal file engine.py
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Macro Dashboard Pro", page_icon="📊", layout="wide")
st.title("🏛️ Global Macro & Liquidity Terminal")

with st.expander("📚 Cruscotto Rapido (Come leggere i dati)"):
    st.markdown("""
    * **Liquidità FED:** Quantità di moneta nel sistema. Se sale, i mercati salgono. Se scende, c'è rischio crollo.
    * **Shiller P/E (CAPE):** Valutazione storica. Se > 30, le azioni sono estremamente costose (Rischio Bolla).
    * **Stagionalità:** Compara l'anno in corso con la media storica. Aiuta a prevedere i periodi "caldi" o "freddi" dell'anno.
    * **Hash Ribbon (On-Chain):** Monitora i minatori di Bitcoin. La "Capitolazione" segna spesso il fondo del mercato.
    * **Smart Money (HYG):** Se le azioni salgono ma l'HYG scende, le banche stanno scaricando rischio di nascosto.
    * **Mayer Multiple (Crypto):** < 1.0 = Zona di Accumulo Storica. > 2.4 = Bolla Speculativa Estrema.
    """)

# --- INIZIALIZZAZIONE E SINCRONIZZAZIONE DATI ---
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

with st.spinner("📊 Sincronizzazione Dati Live e Motori FED..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        hash_status, df_hash = get_onchain_metrics()
        df_etfs = get_etf_screener()
        tension_index, top_news, region_scores = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        supabase_client = init_supabase()
    except Exception as e:
        st.error(f"Errore di connessione ai fornitori dati: {e}")
        st.stop()

if current.empty:
    st.error("Dati storici non disponibili. Riprova tra qualche minuto.")
    st.stop()

# --- CALCOLO STAGIONALITA' ---
df_sp500_corrente, df_sp500_storico = calcola_stagionalita(df, 'S&P 500')

# --- SMART ALERTS (SISTEMA DI ALLARME ISTITUZIONALE) ---
alerts = check_smart_alerts(df, live_prices, tension_index, hash_status)
if alerts:
    st.markdown("---")
    for alert in alerts:
        if "BUY SIGNAL" in alert or "🚀" in alert or "🟢" in alert:
            st.success(f"**{alert}**")
        else:
            st.error(f"**{alert}**")
    st.markdown("---")

# Calcolo fase macro per l'AI
fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)
ai_context = f"Fase Macro: {fase_attuale}, S&P500 Z-Score: {current.get('Z_S&P 500', 0):.2f}, Shiller CAPE: {current.get('CAPE', 0):.2f}, Liquidità FED Delta 30g: {current.get('Liquidity_Delta_30d', 0):.2f}T, Oro Z-Score: {current.get('Z_Oro', 0):.2f}, BTC Mayer: {current.get('Mayer_BTC', 0):.2f}, On-Chain BTC: {hash_status}."

# --- SIDEBAR: STRUMENTI PRO ---
st.sidebar.markdown("---")
def to_excel(dataframe):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    dataframe.to_excel(writer, index=True, sheet_name='Dati_Macro')
    writer.close()
    return output.getvalue()
st.sidebar.download_button("📥 Esporta Dati (Excel)", data=to_excel(df), file_name="macro_data.xlsx", mime="application/vnd.ms-excel")

# --- SIDEBAR: REPORT AI ISTANTANEO ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Analisi Rapida AI")

if st.sidebar.button("🤖 Genera Report Istantaneo", use_container_width=True):
    if "GEMINI_API_KEY" in st.secrets:
        with st.sidebar.status("L'AI sta leggendo i mercati..."):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                # Seleziona il modello veloce
                model_name = next((m.name for m in genai.list_models() if "flash" in m.name.lower()), "gemini-1.5-flash")
                model = genai.GenerativeModel(model_name)
                
                # Chiamata all'AI
                prompt = f"Sei un analista macro. Riassumi i segnali chiave di oggi: {ai_context}. Sii telegrafico, solo segnali operativi."
                risposta = model.generate_content(prompt).text
                
                # SALVIAMO NELLO STATO DELLA SESSIONE
                st.session_state.sidebar_report = risposta
            except Exception as e:
                st.sidebar.error(f"Errore AI: {e}")
    else:
        st.sidebar.error("Chiave API mancante.")

# MOSTRIAMO IL REPORT (Fuori dal blocco del pulsante, così non sparisce)
if "sidebar_report" in st.session_state:
    st.sidebar.info(st.session_state.sidebar_report)
    if st.sidebar.button("🗑️ Cancella Report"):
        del st.session_state.sidebar_report
        st.rerun()
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Automazione Notifiche")
url_id = st.query_params.get("id", "")
bot_link = get_telegram_link()

st.sidebar.markdown(f"""
<a href="{bot_link}" target="_blank" style="text-decoration:none;">
    <button style="width:100%; border-radius:5px; background-color:#24A1DE; color:white; border:none; padding:10px; cursor:pointer; font-weight:bold;">
        🚀 Attiva Bot Telegram
    </button>
</a>
""", unsafe_allow_html=True)

tg_user_id = st.sidebar.text_input("ID Telegram (se manuale):", value=url_id)
if st.sidebar.button("💾 Salva ID nel Database", use_container_width=True):
    if tg_user_id and supabase_client:
        try:
            supabase_client.table("telegram_users").insert({"chat_id": str(tg_user_id)}).execute()
            st.sidebar.success("✅ Sincronizzazione Database completata!")
            st.query_params.clear()
        except Exception as e:
            if "duplicate key" in str(e).lower(): st.sidebar.info("✅ ID già presente nel sistema.")
            else: st.sidebar.error("Errore DB Supabase.")

# ==========================================
# CORPO PRINCIPALE (EX TAB 1: MACROECONOMIA)
# ==========================================

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

# --- OROLOGIO DEL CICLO ECONOMICO ---
st.markdown("---")
st.header("⏱️ Orologio del Ciclo Economico")
fase_orologio, desc_orologio, asset_orologio, colore_orologio = calcola_orologio_ciclo(df)

col_clk1, col_clk2 = st.columns([1, 2])

with col_clk1:
    # Mostriamo la fase attuale con un box colorato
    if colore_orologio == "success":
        st.success(f"**Lancetta Attuale:**\n### {fase_orologio}")
    elif colore_orologio == "warning":
        st.warning(f"**Lancetta Attuale:**\n### {fase_orologio}")
    elif colore_orologio == "error":
        st.error(f"**Lancetta Attuale:**\n### {fase_orologio}")
    else:
        st.info(f"**Lancetta Attuale:**\n### {fase_orologio}")

with col_clk2:
    st.markdown(f"**Scenario:** {desc_orologio}")
    st.markdown(f"**Allocazione Istituzionale Consigliata:** {asset_orologio}")
    st.progress(
        0.25 if "Reflazione" in fase_orologio else 
        0.50 if "Ripresa" in fase_orologio else 
        0.75 if "Surriscaldamento" in fase_orologio else 1.0
    )
    st.caption("Fasi: 25% Reflazione ➔ 50% Ripresa ➔ 75% Surriscaldamento ➔ 100% Stagflazione")

st.markdown("---")
st.header("📅 Cicli e Stagionalità (S&P 500)")
st.write("Confronto tra l'anno in corso e la media storica degli ultimi 20 anni. Permette di capire se il mercato è in anticipo o in ritardo rispetto ai suoi normali flussi di capitale stagionali.")

if not df_sp500_corrente.empty and not df_sp500_storico.empty:
    fig_season = go.Figure()
    anno_ora = pd.Timestamp.now().year
    fig_season.add_trace(go.Scatter(x=df_sp500_corrente['DayOfYear'], y=df_sp500_corrente['Cumulative'], name=f'S&P 500 ({anno_ora})', line=dict(color='#00b894', width=3)))
    fig_season.add_trace(go.Scatter(x=df_sp500_storico['DayOfYear'], y=df_sp500_storico['Cumulative Storico'], name='Media Storica (20 anni)', line=dict(color='#b2bec3', width=2, dash='dash')))
    fig_season.update_layout(height=400, xaxis_title="Giorno dell'Anno (1-365)", yaxis_title="Performance Cumulata (Base 100)", margin=dict(l=0, r=0, t=10, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)'))
    st.plotly_chart(fig_season, use_container_width=True)

st.markdown("---")
st.header("🌊 Fed Liquidity Tracker")
st.write("Analisi di correlazione tra stampa di moneta (FED) e S&P 500.")

if 'Fed_Liquidity_T' in df.columns and 'S&P 500' in df.columns:
    fig_liq = go.Figure()
    fig_liq.add_trace(go.Scatter(x=df.index, y=df['S&P 500'], name='S&P 500', yaxis='y1', line=dict(color='#00b894', width=2)))
    fig_liq.add_trace(go.Scatter(x=df.index, y=df['Fed_Liquidity_T'], name='Net Liquidity ($T)', yaxis='y2', line=dict(color='#0984e3', width=2)))
    fig_liq.update_layout(
        yaxis=dict(title='S&P 500 (Punti)', side='left', showgrid=False),
        yaxis2=dict(title='Liquidità FED ($ Trilioni)', side='right', overlaying='y', showgrid=False),
        height=380, margin=dict(l=0, r=0, t=30, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)')
    )
    st.plotly_chart(fig_liq, use_container_width=True)

st.markdown("---")
st.header("👁️ Smart Money & Divergenze")
col_sm1, col_sm2 = st.columns(2)
with col_sm1:
    st.subheader("🏦 Mercato del Credito (HYG)")
    if current.get('Z_S&P 500', 0) > 0 and current.get('Z_High Yield', 0) < 0: st.error("⚠️ **DIVERGENZA RIBASSISTA:** Le banche vendono rischio.")
    elif current.get('Z_S&P 500', 0) < 0 and current.get('Z_High Yield', 0) > 0: st.success("🟢 **DIVERGENZA RIALZISTA:** Lo Smart Money sta accumulando.")
    else: st.info("⚖️ **CONVERGENZA:** Mercato azionario e credito sono allineati.")
with col_sm2:
    st.subheader("🖨️ Direzione Liquidità")
    if liq_delta > 0: st.success("🟢 **ESPANSIONE (Risk-On):** Il sistema è supportato dalla liquidità.")
    else: st.error("🔴 **CONTRAZIONE (Risk-Off):** La FED drena dollari. Rischio di correzione.")

if not df_etfs.empty:
    st.markdown("---")
    st.header("🗺️ Screener Settoriale & ETF")
    col_g1, col_g2 = st.columns(2)
    with col_g1: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Geografia'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Aree Geografiche").update_layout(coloraxis_showscale=False, height=350), use_container_width=True)
    with col_g2: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Settore'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Settori S&P 500").update_layout(coloraxis_showscale=False, height=350), use_container_width=True)
    st.dataframe(df_etfs[['Asset', 'Categoria', 'Prezzo ($)', 'Perf. 1 Mese (%)', 'Segnale Operativo']].sort_values(by='Perf. 1 Mese (%)', ascending=False), use_container_width=True, hide_index=True)
st.markdown("---")
st.header("📉 Curva dei Rendimenti (Spread T10Y2Y)")
st.write("La differenza tra i tassi a 10 anni e 2 anni. Se scende sotto lo zero (Inversione), il mercato sta segnalando una recessione imminente.")

if 'YieldCurve' in df.columns:
    fig_yield = go.Figure()
    # Linea dello Spread
    fig_yield.add_trace(go.Scatter(
        x=df.index, y=df['YieldCurve'], 
        name='Spread 10Y-2Y',
        line=dict(color='#0984e3', width=2),
        fill='tozeroy', fillcolor='rgba(9, 132, 227, 0.1)'
    ))
    # Linea dello Zero (Riferimento)
    fig_yield.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Area di Recessione")
    
    fig_yield.update_layout(
        height=350, 
        yaxis_title="Percentuale (%)",
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(x=0.01, y=0.99)
    )
    st.plotly_chart(fig_yield, use_container_width=True)

    st.markdown("---")
st.header("😰 Termometro del Panico (VIX vs VIX3M)")
vix_val = live_prices.get('^VIX', current.get('VIX', 0))
vix3m_val = live_prices.get('^VIX3M', 20.0) # Valore di default se manca

col_vix1, col_vix2 = st.columns([1, 2])

with col_vix1:
    ratio = vix_val / vix3m_val
    if ratio > 1:
        st.error(f"### BACKWARDATION\nRatio: {ratio:.2f}")
        st.write("⚠️ **PANICO:** La volatilità a breve è esplosa. Storicamente indica un bottom di mercato.")
    else:
        st.success(f"### CONTANGO\nRatio: {ratio:.2f}")
        st.write("✅ **CALMA:** La struttura è normale. Gli investitori sono tranquilli sul breve periodo.")

with col_vix2:
    fig_vix = go.Figure(go.Bar(
        x=['VIX (1M)', 'VIX3M (3M)'],
        y=[vix_val, vix3m_val],
        marker_color=['#d63031' if ratio > 1 else '#00b894', '#b2bec3']
    ))
    fig_vix.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="Indice Volatilità")
    st.plotly_chart(fig_vix, use_container_width=True)
