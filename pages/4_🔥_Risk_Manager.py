import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import google.generativeai as genai
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Risk Manager Pro", page_icon="🔥", layout="wide")

# --- LOGICA MEMORIA URL (Link Magico) ---
# Recuperiamo i parametri dall'URL se esistono
params = st.query_params

# Inizializziamo la sessione con i valori dell'URL o con i default
if "azioni" not in st.session_state:
    st.session_state.azioni = int(params.get("az", 50))
if "bonds" not in st.session_state:
    st.session_state.bonds = int(params.get("bo", 20))
if "crypto" not in st.session_state:
    st.session_state.crypto = int(params.get("cr", 10))
if "difesa" not in st.session_state:
    st.session_state.difesa = int(params.get("di", 20))

# --- UI PRINCIPALE ---
st.title("🔥 Risk Manager & Intelligence")
st.write("Configura la tua asset allocation. I dati vengono salvati automaticamente nell'URL.")

# 🚨 AVVISO DI SALVATAGGIO URL
st.warning("🔗 **PRO TIP: Salva questa pagina nei preferiti!** Le tue percentuali sono codificate nell'URL. Se vuoi conservare questo portafoglio o condividerlo, ti basta copiare il link del browser.")

# --- CARICAMENTO DATI ---
with st.spinner("Calcolo metriche di rischio..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], 90)
        tension_index, _, _ = analyze_geopolitics()
        hash_status, _ = get_onchain_metrics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)
    except:
        st.error("Errore caricamento dati engine.")
        st.stop()

# --- INPUT ALLOCATION (Collegati alla sessione e all'URL) ---
st.sidebar.header("🎯 Tua Allocazione")

def update_params():
    # Aggiorna l'URL ogni volta che cambiano i valori
    st.query_params.update({
        "az": st.session_state.azioni,
        "bo": st.session_state.bonds,
        "cr": st.session_state.crypto,
        "di": st.session_state.difesa
    })

a1 = st.sidebar.number_input("Azioni (%)", 0, 100, key="azioni", on_change=update_params)
a2 = st.sidebar.number_input("Bonds (%)", 0, 100, key="bonds", on_change=update_params)
a3 = st.sidebar.number_input("Crypto (%)", 0, 100, key="crypto", on_change=update_params)
a4 = st.sidebar.number_input("Difesa (%)", 0, 100, key="difesa", on_change=update_params)

totale = a1 + a2 + a3 + a4

if totale != 100:
    st.sidebar.error(f"Totale: {totale}% (Deve essere 100%)")
else:
    st.sidebar.success("✅ Portafoglio Bilanciato")
    
    # --- BACKTEST STORICO ---
    st.header("📈 Analisi Storica (Backtest)")
    pesi = {'Azioni': a1/100, 'Bonds': a2/100, 'Crypto': a3/100, 'Difesa': a4/100}
    
    eq_port, eq_bench, cagr, max_dd = calcola_backtest(df, pesi)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Capitale Finale", f"${eq_port.iloc[-1]:,.2f}")
    m2.metric("CAGR (Rendimento)", f"{cagr*100:.1f}%")
    m3.metric("Max Drawdown", f"{max_dd*100:.1f}%", delta="Rischio Storico", delta_color="inverse")
    
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(x=eq_port.index, y=eq_port, name='Tuo Portafoglio', line=dict(color='#00b894')))
    fig_hist.add_trace(go.Scatter(x=eq_bench.index, y=eq_bench, name='S&P 500', line=dict(color='#b2bec3', dash='dash')))
    fig_hist.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("---")
    
    # --- SIMULAZIONE MONTE CARLO (FUTURO) ---
    st.header("🔮 Simulazione Monte Carlo (Proiezione 10 Anni)")
    st.write("Abbiamo generato 1.000 scenari futuri casuali basati sulla volatilità storica del tuo portafoglio.")
    
    # Logica semplificata Monte Carlo
    mu = cagr # rendimento medio
    sigma = abs(max_dd) * 0.5 # volatilità stimata
    n_sims = 100
    n_years = 10
    
    sim_results = []
    for _ in range(n_sims):
        prices = [10000]
        for _ in range(n_years):
            prices.append(prices[-1] * (1 + np.random.normal(mu, sigma)))
        sim_results.append(prices)
    
    fig_mc = go.Figure()
    for s in sim_results:
        fig_mc.add_trace(go.Scatter(y=s, mode='lines', line=dict(width=1), opacity=0.1, showlegend=False))
    
    # Mediana
    median_path = np.median(sim_results, axis=0)
    fig_mc.add_trace(go.Scatter(y=median_path, name='Scenario Probabile (Mediana)', line=dict(color='white', width=3)))
    
    fig_mc.update_layout(height=400, yaxis_title="Valore Portafoglio ($)", xaxis_title="Anni")
    st.plotly_chart(fig_mc, use_container_width=True)

    # AI RISK ADVISOR
    if st.button("🚀 Chiedi Analisi Strategica all'AI", use_container_width=True):
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel("gemini-1.5-flash")
            ctx = f"Allocazione: {pesi}. Fase Macro: {fase_attuale}. CAGR: {cagr}. MaxDD: {max_dd}."
            res = model.generate_content(f"Agisci come Risk Manager. Analizza questo portafoglio in base a: {ctx}. Sii critico.").text
            st.info(res)
