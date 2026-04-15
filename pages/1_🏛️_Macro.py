import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from engine import *

st.set_page_config(page_title="Macroeconomia", page_icon="🏛️", layout="wide")
st.title("🏛️ Macroeconomia & Liquidità")

# Caricamento rapido grazie alla cache di engine.py
try:
    df = load_all_data(st.secrets["FRED_API_KEY"], 90)
    current = df.iloc[-1]
    df_etfs = get_etf_screener()
    df_sp500_corrente, df_sp500_storico = calcola_stagionalita(df, 'S&P 500')
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

st.markdown("---")
st.header("📅 Cicli e Stagionalità (S&P 500)")
st.write("Confronto tra l'anno in corso e la media storica degli ultimi 20 anni.")

if not df_sp500_corrente.empty and not df_sp500_storico.empty:
    fig_season = go.Figure()
    anno_ora = pd.Timestamp.now().year
    fig_season.add_trace(go.Scatter(x=df_sp500_corrente['DayOfYear'], y=df_sp500_corrente['Cumulative'], name=f'S&P 500 ({anno_ora})', line=dict(color='#00b894', width=3)))
    fig_season.add_trace(go.Scatter(x=df_sp500_storico['DayOfYear'], y=df_sp500_storico['Cumulative Storico'], name='Media Storica (20 anni)', line=dict(color='#b2bec3', width=2, dash='dash')))
    fig_season.update_layout(height=400, xaxis_title="Giorno dell'Anno (1-365)", yaxis_title="Performance Cumulata (Base 100)", margin=dict(l=0, r=0, t=10, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)'))
    st.plotly_chart(fig_season, use_container_width=True)

st.markdown("---")
st.header("🌊 Fed Liquidity Tracker")
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
    liq_delta = current.get('Liquidity_Delta_30d', 0)
    if liq_delta > 0: st.success("🟢 **ESPANSIONE (Risk-On):** Il sistema è supportato dalla liquidità.")
    else: st.error("🔴 **CONTRAZIONE (Risk-Off):** La FED drena dollari. Rischio di correzione.")

if not df_etfs.empty:
    st.markdown("---")
    st.header("🗺️ Screener Settoriale & ETF")
    col_g1, col_g2 = st.columns(2)
    with col_g1: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Geografia'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Aree Geografiche").update_layout(coloraxis_showscale=False, height=350), use_container_width=True)
    with col_g2: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Settore'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Settori S&P 500").update_layout(coloraxis_showscale=False, height=350), use_container_width=True)
    st.dataframe(df_etfs[['Asset', 'Categoria', 'Prezzo ($)', 'Perf. 1 Mese (%)', 'Segnale Operativo']].sort_values(by='Perf. 1 Mese (%)', ascending=False), use_container_width=True, hide_index=True)
