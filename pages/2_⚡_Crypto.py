import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Crypto & On-Chain", page_icon="⚡", layout="wide")
st.title("⚡ Crypto & On-Chain Analysis")
st.write("Metriche avanzate, analisi della redditività dei minatori e valutazione matematica del ciclo di mercato.")

# --- CARICAMENTO DATI (Istanteo tramite Cache) ---
lookback = 90
with st.spinner("Sincronizzazione dati Blockchain..."):
    try:
        # Carichiamo solo ciò che è strettamente necessario per questa pagina
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        hash_status, df_hash = get_onchain_metrics()
        df_crypto = get_crypto_screener()
        fgi_val, fgi_class = get_crypto_fgi()
        current = df.iloc[-1] if not df.empty else pd.Series()
        df_btc_corrente, df_btc_storico = calcola_stagionalita(df, 'Bitcoin')
    except Exception as e:
        st.error(f"Errore tecnico nel caricamento dati: {e}")
        st.stop()

if current.empty:
    st.warning("Dati storici non disponibili al momento.")
    st.stop()

# ==========================================
# CORPO DELLA PAGINA CRYPTO E ON-CHAIN
# ==========================================

st.header("⚡ Valutazione Ciclo Bitcoin")
mayer_btc = current.get('Mayer_BTC', 0)
col_pre1, col_pre2 = st.columns(2)

with col_pre1:
    st.subheader("Fase Macro (Mayer Multiple)")
    if mayer_btc < 1.0: st.success("🔋 **ACCUMULO (Sconto Storico)**")
    elif mayer_btc < 2.0: st.warning("📈 **BULL MARKET (Trend Sano)**")
    else: st.error("💥 **BOLLA SPECULATIVA (Prendere Profitti)**")

with col_pre2:
    st.plotly_chart(go.Figure(go.Indicator(
        mode="gauge+number", 
        value=fgi_val, 
        title={'text': f"Fear & Greed Index: {fgi_class}"}, 
        gauge={
            'axis': {'range': [0, 100]}, 
            'steps': [{'range': [0, 45], 'color': "#e57373"}, {'range': [55, 100], 'color': "#81c784"}]
        }
    )).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)

c1, c2, c3, c4 = st.columns(4)
btc_live = live_prices.get('BTC-USD', current.get('Bitcoin', 0))
c1.metric("Prezzo BTC (Live)", f"${btc_live:,.0f}")
c2.metric("Mayer Multiple", f"{mayer_btc:.2f}")
c3.metric("RSI (14 Giorni)", f"{current.get('RSI_BTC', 0):.0f}")
c4.metric("Distanza da ATH", f"{current.get('BTC_Drawdown', 0):.1f}%")

st.markdown("---")
st.header("📅 Stagionalità (Bitcoin)")
st.write("L'andamento di Bitcoin nel corso dell'anno attuale rispetto alla media storica decennale.")

if not df_btc_corrente.empty and not df_btc_storico.empty:
    fig_btc_season = go.Figure()
    anno_ora_btc = pd.Timestamp.now().year
    fig_btc_season.add_trace(go.Scatter(x=df_btc_corrente['DayOfYear'], y=df_btc_corrente['Cumulative'], name=f'Bitcoin ({anno_ora_btc})', line=dict(color='#fdcb6e', width=3)))
    fig_btc_season.add_trace(go.Scatter(x=df_btc_storico['DayOfYear'], y=df_btc_storico['Cumulative Storico'], name='Media Storica', line=dict(color='#b2bec3', width=2, dash='dash')))
    fig_btc_season.update_layout(height=400, xaxis_title="Giorno dell'Anno (1-365)", yaxis_title="Performance Cumulata (Base 100)", margin=dict(l=0, r=0, t=10, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)'))
    st.plotly_chart(fig_btc_season, use_container_width=True)

st.markdown("---")
st.header("⛓️ Analisi On-Chain: Hash Ribbon")
st.write("Misura la salute della rete Bitcoin e la redditività dei Minatori. Quando la media veloce scende sotto la lenta, i minatori stanno capitolando (ottimo setup di lungo termine).")

if "CAPITULATION" in hash_status:
    st.error(f"**Stato Rete Attuale:** {hash_status}")
elif "BUY SIGNAL" in hash_status:
    st.success(f"**Stato Rete Attuale:** {hash_status}")
else:
    st.info(f"**Stato Rete Attuale:** {hash_status}")
    
if not df_hash.empty:
    fig_hash = go.Figure()
    fig_hash.add_trace(go.Scatter(x=df_hash.index, y=df_hash['SMA30'], name='SMA 30 (Veloce)', line=dict(color='#ff7675', width=2)))
    fig_hash.add_trace(go.Scatter(x=df_hash.index, y=df_hash['SMA60'], name='SMA 60 (Lenta)', line=dict(color='#0984e3', width=2)))
    fig_hash.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)'), yaxis_title="Terahashes/s")
    st.plotly_chart(fig_hash, use_container_width=True)

if not df_crypto.empty: 
    st.markdown("---")
    st.subheader("Screener Altcoin (Rotazione 1M)")
    st.plotly_chart(px.bar(df_crypto, x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn').update_layout(coloraxis_showscale=False, height=350), use_container_width=True)
