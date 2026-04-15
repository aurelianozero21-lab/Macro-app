import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Geopolitica & Materie Prime", page_icon="🌍", layout="wide")
st.title("🌍 Radar Geopolitico e Rischio Globale")
st.write("Analisi NLP (Natural Language Processing) delle notizie globali in tempo reale e monitoraggio dei beni rifugio.")

# --- CARICAMENTO DATI (Istanteo tramite Cache) ---
lookback = 90
with st.spinner("Scansione delle fonti geopolitiche internazionali..."):
    try:
        # Carichiamo solo i dati necessari per questa sezione
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        tension_index, top_news, region_scores = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
    except Exception as e:
        st.error(f"Errore tecnico nel caricamento dati: {e}")
        st.stop()

# ==========================================
# CORPO PRINCIPALE (EX TAB 3: GEOPOLITICA)
# ==========================================

col_g1, col_g2, col_g3 = st.columns([1.5, 1, 1.2])

with col_g1: 
    st.plotly_chart(go.Figure(go.Indicator(
        mode="gauge+number", 
        value=tension_index, 
        title={'text': "Tensione Globale (NLP AI)"}, 
        gauge={
            'axis': {'range': [0, 100]}, 
            'steps': [{'range': [0, 40], 'color': "#81c784"}, 
                      {'range': [40, 60], 'color': "#ffb74d"}, 
                      {'range': [60, 100], 'color': "#e57373"}]
        }
    )).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)

with col_g2:
    st.subheader("🗺️ Mappa Focolai")
    for region, count in region_scores.items(): 
        st.metric(region, f"{count} Alert Stampa", delta="🔥 Tensione Alta" if count >= 2 else "Calmo", delta_color="inverse" if count >= 2 else "normal")

with col_g3:
    st.subheader("🛢️ Beni Rifugio Live")
    gold_live = live_prices.get('GC=F', current.get('Oro', 0))
    oil_live = live_prices.get('CL=F', 0.0)
    z_oro = current.get('Z_Oro', 0)
    
    st.metric("Oro / Oncia", f"${gold_live:,.1f}", delta=f"Z-Score Trend: {z_oro:.2f}", delta_color="inverse" if z_oro > 1 else "normal")
    st.metric("Petrolio WTI / Barile", f"${oil_live:,.2f}", delta="Termometro Inflazione", delta_color="off")

if top_news:
    st.markdown("---")
    st.subheader("📰 Ultime Notizie Analizzate")
    for item in top_news: 
        st.markdown(f"- **[{'🔴 Rischio' if item['score'] > 0 else '🟢 Distensione'}]** [{item['titolo']}]({item['link']})")
