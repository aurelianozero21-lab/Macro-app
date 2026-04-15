import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Macroeconomia", page_icon="🏛️", layout="wide")
st.title("🏛️ Macro & Liquidity")
st.write("Analisi approfondita dei flussi di capitale, liquidità istituzionale e stagionalità.")

# --- CARICAMENTO DATI (Istanteo tramite Cache) ---
lookback = 90
with st.spinner("Sincronizzazione dati Macro..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        df_etfs = get_etf_screener()
        tension_index, _, _ = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        
        # Variabili calcolate
        fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)
        liq_delta = current.get('Liquidity_Delta_30d', 0)
        df_sp500_corrente, df_sp500_storico = calcola_stagionalita(df, 'S&P 500')
    except Exception as e:
        st.error(f"Errore tecnico nel caricamento dati: {e}")
        st.stop()

if current.empty:
    st.warning("Dati non disponibili al momento.")
    st.stop()

# ==========================================
# CORPO DELLA PAGINA MACRO
# ==========================================

st.header("🚦 Semaforo Macro Intelligente")
if "1." in fase_attuale: st.error(f"🚨 **FASE DI MERCATO: {fase_attuale}**")
elif "2." in fase_attuale: st.warning(f"⚖️ **FASE DI MERCATO: {fase_attuale}**")
else: st.success(f"🚀 **FASE DI MERCATO: {fase_attuale}**")

col_live1, col_live2, col_live3, col_live4 = st.columns(4)
sp500_live = live_prices.get('^GSPC', current.get('S&P 500', 0))
vix_live = live_prices.get('^VIX', current.get('VIX', 0))
cape_val = current.get('CAPE', 0)

col_live1.metric("S&P 500 (Live)", f"{sp500_live:,.2f}", delta=f"Z-Score: {current.get('Z_S&P 500', 0):.2f}")
col_live2.metric("Liquidità FED Netta", f"${current.get('Fed_Liquidity_T', 0):.2f}T", delta=f"{'+' if liq_delta > 0 else ''}{liq_delta:.2f}T (30g)", delta_color="normal")
col_live3.metric("Shiller P/E (CAPE)", f"{cape_val:.2f}", delta="> 30 Rischio Bolla", delta_color="inverse" if cape_val > 30 else "normal")
col_live4.metric("VIX Index (Paura)", f"{vix_live:.2f}", delta="Volatilità", delta_color="off")

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
