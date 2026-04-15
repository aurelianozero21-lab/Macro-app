import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Geopolitica & Rischio", page_icon="🌍", layout="wide")
st.title("🌍 Radar Geopolitico e Supply Chain")
st.write("Analisi NLP (Natural Language Processing) delle notizie globali e tracking dei flussi di capitale difensivi.")

# --- CARICAMENTO DATI (Istantaneo tramite Cache) ---
lookback = 90
with st.spinner("Scansione dei radar internazionali e dei mercati valutari..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        tension_index, top_news, region_scores = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        
        # Recupero dati extra per la geopolitica (con fallback)
        dxy_live = live_prices.get('DX-Y.NYB', 104.50)
        gold_live = live_prices.get('GC=F', current.get('Oro', 0))
        oil_live = live_prices.get('CL=F', 80.0)
    except Exception as e:
        st.error(f"Errore tecnico nel caricamento dati: {e}")
        st.stop()

# ==========================================
# 1. INDICE DI TENSIONE E BENI RIFUGIO
# ==========================================
st.header("🌐 Rischio Sistemico e Safe Havens")

col_g1, col_g2, col_g3, col_g4 = st.columns([1.5, 1, 1, 1])

with col_g1: 
    st.plotly_chart(go.Figure(go.Indicator(
        mode="gauge+number", 
        value=tension_index, 
        title={'text': "Tensione Globale (NLP AI)"}, 
        gauge={
            'axis': {'range': [0, 100]}, 
            'steps': [{'range': [0, 40], 'color': "#00b894"}, 
                      {'range': [40, 60], 'color': "#fdcb6e"}, 
                      {'range': [60, 100], 'color': "#d63031"}],
            'bar': {'color': "black"}
        }
    )).update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)

with col_g2:
    z_oro = current.get('Z_Oro', 0)
    st.metric("Oro / Oncia (Assicurazione)", f"${gold_live:,.1f}", delta=f"Z-Score Trend: {z_oro:.2f}", delta_color="inverse" if z_oro > 1 else "normal")
    st.caption("Protezione contro inflazione e caos.")

with col_g3:
    st.metric("Petrolio WTI (Supply Chain)", f"${oil_live:,.2f}", delta="Termometro Conflitti", delta_color="off")
    st.caption("Altamente sensibile al Medio Oriente.")

with col_g4:
    # Il Dollaro Index (DXY)
    st.metric("US Dollar Index (DXY)", f"{dxy_live:.2f}", delta="Liquidity Drain", delta_color="off")
    st.caption("Se sale forte, i mercati crollano (Wrecking Ball).")

st.markdown("---")

# ==========================================
# 2. WAR ECONOMY TRACKER E FOCOLAI
# ==========================================
col_w1, col_w2 = st.columns([2, 1])

with col_w1:
    st.header("🛡️ War Economy Tracker")
    st.write("Analisi dei flussi di capitale istituzionali. Se il settore Difesa sovraperforma l'S&P 500, le grandi banche stanno prezzando un'escalation militare reale, ignorando le rassicurazioni politiche.")
    
    # Recuperiamo l'ETF Aerospazio/Difesa (ITA) vs S&P500 se disponibili nei live_prices, o simuliamo l'allarme
    ita_perf = live_prices.get('ITA_1M_Perf', 2.5) # Dati simulati/estratti per la demo
    sp500_perf = live_prices.get('SPY_1M_Perf', 1.2)
    
    if ita_perf > sp500_perf + 2.0:
        st.error(f"🚨 **ALLARME FLUSSI:** Il settore Difesa sta battendo pesantemente il mercato azionario globale (+{ita_perf:.1f}% vs +{sp500_perf:.1f}%). I capitali si preparano a un'escalation.")
    elif ita_perf > sp500_perf:
        st.warning(f"🟡 **ATTENZIONE:** Lieve rotazione di capitali verso i titoli militari (+{ita_perf:.1f}%). Tensione in accumulo.")
    else:
        st.success(f"🟢 **DISTENSIONE:** Il mercato generale sovraperforma la Difesa. I grandi fondi NON stanno prezzando guerre globali in questo momento.")

with col_w2:
    st.subheader("🗺️ Mappa Focolai Caldi")
    if region_scores:
        for region, count in region_scores.items(): 
            st.metric(region, f"{count} Alert Stampa", delta="🔥 Tensione Alta" if count >= 2 else "Stabile", delta_color="inverse" if count >= 2 else "normal")
    else:
        st.info("Nessun focolaio anomalo rilevato nelle ultime 24h.")

# ==========================================
# 3. FEED NOTIZIE NLP
# ==========================================
if top_news:
    st.markdown("---")
    st.header("📰 Newsfeed Analizzato dall'AI")
    st.write("Le ultime notizie globali processate dal motore di analisi del linguaggio naturale (NLP).")
    
    for item in top_news: 
        # Formattazione visiva in base al punteggio di rischio (score)
        if item['score'] > 0:
            st.markdown(f"🔴 **Rischio Escalation** | [{item['titolo']}]({item['link']})")
        else:
            st.markdown(f"🟢 **Diplomazia / Neutrale** | [{item['titolo']}]({item['link']})")
