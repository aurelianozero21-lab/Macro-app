import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Risk Manager Pro", page_icon="🔥", layout="wide")

# --- LOGICA MEMORIA URL (Link Magico) ---
params = st.query_params
if "azioni" not in st.session_state:
    st.session_state.azioni = int(params.get("az", 50))
if "bonds" not in st.session_state:
    st.session_state.bonds = int(params.get("bo", 20))
if "crypto" not in st.session_state:
    st.session_state.crypto = int(params.get("cr", 10))
if "difesa" not in st.session_state:
    st.session_state.difesa = int(params.get("di", 20))

st.title("🔥 Risk Manager & Intelligence")
st.warning("🔗 **PRO TIP:** Salva questa pagina nei preferiti per non perdere le tue percentuali di allocazione!")

# --- CARICAMENTO DATI ---
with st.spinner("Sincronizzazione motori di rischio..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], 90)
        tension_index, _, _ = analyze_geopolitics()
        current = df.iloc[-1]
        # Selezioniamo solo le colonne degli asset per la correlazione
        assets_cols = ['S&P 500', 'Bitcoin', 'Oro', 'YieldCurve'] 
        df_assets = df[assets_cols].dropna()
    except:
        st.error("Errore nel caricamento dei dati storici.")
        st.stop()

# --- SIDEBAR INPUT ---
def update_params():
    st.query_params.update({
        "az": st.session_state.azioni, "bo": st.session_state.bonds,
        "cr": st.session_state.crypto, "di": st.session_state.difesa
    })

st.sidebar.header("🎯 Tua Allocazione")
a1 = st.sidebar.number_input("Azioni (%)", 0, 100, key="azioni", on_change=update_params)
a2 = st.sidebar.number_input("Bonds (%)", 0, 100, key="bonds", on_change=update_params)
a3 = st.sidebar.number_input("Crypto (%)", 0, 100, key="crypto", on_change=update_params)
a4 = st.sidebar.number_input("Difesa (%)", 0, 100, key="difesa", on_change=update_params)

if (a1+a2+a3+a4) == 100:
    # --- MATRICE DI CORRELAZIONE ---
    st.header("🧬 Matrice di Correlazione")
    st.write("Analizza come gli asset si muovono tra loro. Se la correlazione è vicina a 1, gli asset cadono insieme. Se è vicina a -1, uno protegge l'altro.")
    
    corr_matrix = df_assets.corr()
    fig_corr = px.imshow(
        corr_matrix, 
        text_auto=".2f", 
        color_continuous_scale='RdBu_r', 
        aspect="auto",
        labels=dict(color="Correlazione")
    )
    st.plotly_chart(fig_corr, use_container_width=True)

    # --- MONTE CARLO & BACKTEST (Manteniamo i blocchi precedenti qui sotto) ---
    st.markdown("---")
    st.header("🔮 Proiezioni Future (Monte Carlo)")
    # ... (Codice Monte Carlo visto in precedenza) ...
