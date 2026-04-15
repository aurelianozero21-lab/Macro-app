import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Risk Manager Pro", page_icon="🔥", layout="wide")

# --- 1. LOGICA MEMORIA URL (Link Magico) ---
# Recuperiamo i parametri dall'URL (se l'utente ha usato un link salvato)
params = st.query_params

# Inizializziamo lo stato della sessione (Session State)
# Se i parametri esistono nell'URL, usiamo quelli. Altrimenti usiamo i default.
if "azioni" not in st.session_state:
    st.session_state.azioni = int(params.get("az", 50))
if "bonds" not in st.session_state:
    st.session_state.bonds = int(params.get("bo", 20))
if "crypto" not in st.session_state:
    st.session_state.crypto = int(params.get("cr", 10))
if "cash" not in st.session_state:
    st.session_state.cash = int(params.get("ca", 20))

# Funzione per aggiornare l'URL in tempo reale quando l'utente muove i cursori
def update_params():
    st.query_params.update({
        "az": st.session_state.azioni,
        "bo": st.session_state.bonds,
        "cr": st.session_state.crypto,
        "ca": st.session_state.cash
    })

# --- UI PRINCIPALE ---
st.title("🔥 Risk Manager & Intelligence")
st.write("Configura la tua asset allocation. I parametri vengono salvati istantaneamente nel tuo browser.")

# Messaggio PRO TIP per l'utente
st.warning("🔗 **PRO TIP: Salva questa pagina nei preferiti!** Le tue percentuali sono codificate nell'URL. Se vuoi conservare questo portafoglio o condividerlo con qualcuno, copia semplicemente il link che vedi in alto nel browser.")

# --- CARICAMENTO DATI ---
with st.spinner("Calcolo metriche di rischio istituzionali..."):
    try:
        # Carichiamo gli ultimi 90 giorni di dati per l'analisi
        df = load_all_data(st.secrets["FRED_API_KEY"], 90)
        tension_index, _, _ = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)
    except Exception as e:
        st.error(f"Errore tecnico nel motore di calcolo: {e}")
        st.stop()

# --- SIDEBAR: ALLOCAZIONE ---
st.sidebar.header("🎯 Tua Allocazione")
st.sidebar.write("Modifica le percentuali per vedere l'impatto sul rischio.")

# I widget sono collegati al Session State e attivano update_params al cambio
a1 = st.sidebar.number_input("Azioni (%)", 0, 100, key="azioni", on_change=update_params)
a2 = st.sidebar.number_input("Bonds (%)", 0, 100, key="bonds", on_change=update_params)
a3 = st.sidebar.number_input("Crypto (%)", 0, 100, key="crypto", on_change=update_params)
a4 = st.sidebar.number_input("Cash (%)", 0, 100, key="cash", on_change=update_params)

totale = a1 + a2 + a3 + a4

if totale != 100:
    st.sidebar.error(f"Totale: {totale}% (Deve essere 100%)")
    st.info("Regola le percentuali finché il totale non raggiunge il 100%.")
else:
    st.sidebar.success("✅ Portafoglio Bilanciato")
    
    # Prepariamo i pesi per il backtest
    pesi = {'Azioni': a1/100, 'Bonds': a2/100, 'Crypto': a3/100, 'Cash': a4/100}

    # ==========================================
    # 2. ANALISI STORICA (BACKTEST)
    # ==========================================
    st.header("📈 Analisi Storica (Backtest)")
    
    eq_port, eq_bench, cagr, max_dd = calcola_backtest(df, pesi)
    
    # SALVAVITA: Se i dati sono vuoti a causa di un errore API, ferma il crash
    if eq_port.empty or len(eq_port) == 0:
        st.warning("⚠️ Dati di mercato attualmente non disponibili per il calcolo. Verifica le chiavi API o la connessione.")
    else:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Valore Finale (su $10k)", f"${eq_port.iloc[-1]:,.2f}")
        col_m2.metric("CAGR (Rendimento Annuo)", f"{cagr*100:.1f}%")
        col_m3.metric("Max Drawdown (Rischio)", f"{max_dd*100:.1f}%", delta="Perdita Max", delta_color="inverse")
        
        fig_backtest = go.Figure()
        fig_backtest.add_trace(go.Scatter(x=eq_port.index, y=eq_port, name='Tuo Portafoglio', line=dict(color='#00b894', width=3)))
        fig_backtest.add_trace(go.Scatter(x=eq_bench.index, y=eq_bench, name='S&P 500 (Benchmark)', line=dict(color='#b2bec3', dash='dash')))
        fig_backtest.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0), legend=dict(x=0.01, y=0.99))
        st.plotly_chart(fig_backtest, use_container_width=True)

    st.markdown("---")

    # ==========================================
    # 3. MATRICE DI CORRELAZIONE
    # ==========================================
    st.header("🧬 Matrice di Correlazione")
    st.write("Se gli asset sono troppo correlati (vicini a 1.00), il tuo portafoglio non è davvero diversificato.")
    
    # Selezioniamo i ticker rappresentativi per la matrice
    df_corr = df[['S&P 500', 'Bitcoin', 'Oro', 'YieldCurve']].pct_change().corr()
    
    fig_corr = px.imshow(
        df_corr, 
        text_auto=".2f", 
        color_continuous_scale='RdBu_r', 
        labels=dict(color="Correlazione")
    )
    fig_corr.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_corr, use_container_width=True)

    st.markdown("---")

    # ==========================================
    # 4. SIMULAZIONE MONTE CARLO (FUTURO)
    # ==========================================
    st.header("🔮 Simulazione Monte Carlo (10 Anni)")
    st.write("Proiezione statistica di 1.000 possibili futuri basati sulla volatilità attuale del tuo mix.")
    
    # Parametri simulazione
    mu = cagr 
    vol = abs(max_dd) * 0.5 # Stima prudenziale della volatilità
    n_anni = 10
    n_sim = 100 # Numero di linee visualizzate (per velocità)
    
    risultati_sim = []
    for _ in range(n_sim):
        percorso = [10000]
        for _ in range(n_anni):
            rendimento_random = np.random.normal(mu, vol)
            percorso.append(percorso[-1] * (1 + rendimento_random))
        risultati_sim.append(percorso)
    
    fig_monte = go.Figure()
    for p in risultati_sim:
        fig_monte.add_trace(go.Scatter(y=p, mode='lines', line=dict(width=1), opacity=0.1, showlegend=False))
    
    # Linea della Mediana (Scenario più probabile)
    mediana = np.median(risultati_sim, axis=0)
    fig_monte.add_trace(go.Scatter(y=mediana, name='Scenario Mediano', line=dict(color='white', width=4)))
    
    fig_monte.update_layout(height=450, yaxis_title="Valore stimato ($)", xaxis_title="Anni nel futuro", margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_monte, use_container_width=True)

    st.markdown("---")

    # ==========================================
    # 5. AI RISK ADVISOR
    # ==========================================
    st.header("🤖 AI Strategic Review")
    if st.button("Analizza Portafoglio con Intelligenza Artificiale", use_container_width=True):
        if "GEMINI_API_KEY" in st.secrets:
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel("gemini-1.5-flash")
                
                prompt = f"""
                Agisci come un Chief Risk Officer di un Hedge Fund.
                Analizza questa allocazione: {pesi}.
                Dati di mercato attuali: Fase {fase_attuale}.
                Performance storica del portafoglio: Rendimento {cagr*100:.1f}%, Drawdown {max_dd*100:.1f}%.
                
                Fornisci un'analisi critica:
                1. Qual è il rischio principale di questo mix nella fase attuale?
                2. Suggerisci un aggiustamento tattico se necessario.
                Sii professionale, asciutto e diretto.
                """
                
                with st.spinner("L'AI sta interrogando i mercati..."):
                    risposta = model.generate_content(prompt).text
                    st.info(risposta)
            except Exception as e:
                st.error(f"Errore AI: {e}")
        else:
            st.error("Configura la chiave API di Gemini per attivare l'analista.")
