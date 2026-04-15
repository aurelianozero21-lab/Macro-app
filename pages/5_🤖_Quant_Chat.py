import streamlit as st
import pandas as pd
import google.generativeai as genai
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Quant Chat AI", page_icon="🤖", layout="wide")
st.title("🤖 Quant AI Assistant")
st.write("Interroga la tua intelligenza artificiale. L'assistente legge in background tutti i dati della tua dashboard (S&P 500, Liquidità FED, On-Chain, Geopolitica) per darti risposte contestualizzate al millisecondo.")

# --- CARICAMENTO CONTESTO MACRO IN BACKGROUND ---
# Carichiamo i dati di nascosto per darli "in pasto" all'AI
with st.spinner("Sincronizzazione del cervello AI con i mercati live..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], 90)
        tension_index, _, _ = analyze_geopolitics()
        hash_status, _ = get_onchain_metrics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)
        liq_delta = current.get('Liquidity_Delta_30d', 0)
    except Exception as e:
        st.error(f"Errore tecnico nel caricamento dati: {e}")
        st.stop()

# Costruiamo la "memoria" che passeremo all'AI ad ogni domanda
ai_context = f"Fase Macro: {fase_attuale}, S&P500 Z-Score: {current.get('Z_S&P 500', 0):.2f}, Shiller CAPE: {current.get('CAPE', 0):.2f}, Liquidità FED Delta 30g: {liq_delta:.2f}T, Oro Z-Score: {current.get('Z_Oro', 0):.2f}, BTC Mayer: {current.get('Mayer_BTC', 0):.2f}, On-Chain BTC: {hash_status}."

st.markdown("---")

# ==========================================
# CORPO PRINCIPALE (EX TAB 5: AI CHATBOT)
# ==========================================

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Cerca il modello più veloce disponibile
    mod = next((m.name for m in genai.list_models() if "flash" in m.name.lower()), "gemini-1.5-flash")
    
    # Inizializza la cronologia della chat se non esiste
    if "chat_history" not in st.session_state: 
        st.session_state.chat_history = []
        # Messaggio di benvenuto automatico
        st.session_state.chat_history.append({"role": "assistant", "content": "Ciao! Sono il tuo assistente Quantitativo. Ho appena scannerizzato i dati live e i flussi di liquidità. Come posso aiutarti oggi?"})
    
    # Mostra la cronologia
    for m in st.session_state.chat_history: 
        st.chat_message(m["role"]).markdown(m["content"])
    
    # Input dell'utente
    if prompt := st.chat_input("Es: C'è una divergenza pericolosa tra mercato azionario e HYG oggi?"):
        # Aggiunge e mostra la domanda dell'utente
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)
        
        # Interroga Gemini passandogli il contesto invisibile
        with st.spinner("Elaborazione istituzionale in corso..."):
            try:
                full_prompt = f"Contesto Dati Live Attuali (Usali per rispondere, ma non elencarli a meno che non ti venga chiesto esplicitamente): {ai_context}\n\nDomanda dell'utente: {prompt}"
                res = genai.GenerativeModel(mod).generate_content(full_prompt).text
                
                # Aggiunge e mostra la risposta
                st.chat_message("assistant").markdown(res)
                st.session_state.chat_history.append({"role": "assistant", "content": res})
            except Exception as e:
                st.error(f"Errore di comunicazione con l'AI: {e}")

else: 
    st.error("Manca la chiave `GEMINI_API_KEY` nei Secrets di Streamlit.")
