import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Risk Manager", page_icon="🔥", layout="wide")
st.title("🔥 Risk Manager & Backtest Matematico")
st.write("Inserisci l'allocazione del tuo capitale. Il motore simulerà le performance storiche a partire da 10.000$ e l'AI valuterà le vulnerabilità.")

# --- CARICAMENTO DATI (Istanteo tramite Cache) ---
lookback = 90
with st.spinner("Sincronizzazione dati per il Backtest..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        hash_status, _ = get_onchain_metrics()
        tension_index, _, _ = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)
    except Exception as e:
        st.error(f"Errore tecnico nel caricamento dati: {e}")
        st.stop()

# ==========================================
# CORPO PRINCIPALE (EX TAB 4: RISK MANAGER)
# ==========================================

col_p1, col_p2, col_p3, col_p4 = st.columns(4)
with col_p1: alloc_azioni = st.number_input("Azioni / ETF (%)", min_value=0, max_value=100, value=50)
with col_p2: alloc_obbligazioni = st.number_input("Bonds (%)", min_value=0, max_value=100, value=20)
with col_p3: alloc_crypto = st.number_input("Crypto (%)", min_value=0, max_value=100, value=10)
with col_p4: alloc_difesa = st.number_input("Oro / Cash (%)", min_value=0, max_value=100, value=20)

totale = alloc_azioni + alloc_obbligazioni + alloc_crypto + alloc_difesa
if totale != 100:
    st.warning(f"⚠️ Attenzione: Il totale dell'allocazione è {totale}%. Modifica i valori per arrivare a 100%.")
else:
    st.markdown("---")
    st.subheader("📈 Analisi Storica (Equity Curve)")
    
    pesi_utente = {
        'Azioni': alloc_azioni / 100.0,
        'Bonds': alloc_obbligazioni / 100.0,
        'Crypto': alloc_crypto / 100.0,
        'Difesa': alloc_difesa / 100.0
    }
    
    try:
        # Funzione dal motore engine.py
        equity_portafoglio, equity_sp500, cagr, max_dd = calcola_backtest(df, pesi_utente)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Valore Capitale Finale", f"${equity_portafoglio.iloc[-1]:,.2f}")
        col_m2.metric("Rendimento Medio Annuo (CAGR)", f"{cagr*100:.2f}%")
        col_m3.metric("Perdita Massima (Max Drawdown)", f"{max_dd*100:.2f}%", delta="Stress Storico", delta_color="inverse")
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=equity_portafoglio.index, y=equity_portafoglio, name='Tuo Portafoglio', line=dict(color='#00b894', width=2)))
        fig_bt.add_trace(go.Scatter(x=equity_sp500.index, y=equity_sp500, name='S&P 500 (Benchmark)', line=dict(color='#b2bec3', width=1, dash='dash')))
        fig_bt.update_layout(height=400, yaxis_title="Capitale Accumulato ($)", margin=dict(l=0, r=0, t=10, b=0), legend=dict(x=0.01, y=0.99))
        st.plotly_chart(fig_bt, use_container_width=True)
    except Exception as e:
        st.error(f"Errore calcolo backtest: Assicurati di avere tutti i dati storici caricati ({e})")

st.markdown("---")
if st.button("🚀 Richiedi Valutazione Rischio AI", use_container_width=True):
    if "GEMINI_API_KEY" in st.secrets:
        with st.spinner("I Modelli Quantitativi AI stanno elaborando il rischio..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            mod = next((m.name for m in genai.list_models() if "flash" in m.name.lower() or "pro" in m.name.lower()), "gemini-1.5-flash")
            
            # Ricostruiamo il contesto macro per l'AI
            ai_context = f"Fase Macro: {fase_attuale}, S&P500 Z-Score: {current.get('Z_S&P 500', 0):.2f}, Shiller CAPE: {current.get('CAPE', 0):.2f}, Liquidità FED Delta 30g: {current.get('Liquidity_Delta_30d', 0):.2f}T, Oro Z-Score: {current.get('Z_Oro', 0):.2f}, BTC Mayer: {current.get('Mayer_BTC', 0):.2f}, On-Chain BTC: {hash_status}."
            
            prompt = f"Agisci come un Risk Manager Istituzionale. Il portafoglio del cliente è: Azioni {alloc_azioni}%, Bond {alloc_obbligazioni}%, Crypto {alloc_crypto}%, Difesa {alloc_difesa}%. Il contesto macro attuale è: {ai_context}. Fornisci un'analisi spietata sulle vulnerabilità di questa allocazione e suggerisci delle ottimizzazioni. Usa il Markdown e sii professionale."
            
            response = genai.GenerativeModel(mod).generate_content(prompt).text
            st.markdown(response)
    else: 
        st.error("Manca la GEMINI_API_KEY nei Secrets.")
