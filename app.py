import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# Impostazioni della pagina web
st.set_page_config(page_title="Macro Dashboard", layout="wide")
st.title("📊 Global Macro Dashboard (Prototipo v1)")
st.write("Questa app calcola lo Z-Score in tempo reale per capire la propensione al rischio del mercato.")

# Dizionario degli asset da monitorare (Tickers di Yahoo Finance)
assets = {
    'S&P 500 (Rischio)': '^GSPC', 
    'Oro (Rifugio)': 'GC=F', 
    'Treasury 10Y (Rendimenti)': '^TNX', 
    'VIX (Paura)': '^VIX'
}

# Creazione della barra laterale per i parametri
st.sidebar.header("Parametri Matematici")
lookback = st.sidebar.slider("Giorni per Media Mobile (Z-Score)", min_value=30, max_value=200, value=90)

# Funzione per scaricare i dati (viene memorizzata in cache per velocità)
@st.cache_data
def get_data():
    df = pd.DataFrame()
    for name, ticker in assets.items():
        ticker_data = yf.Ticker(ticker)
        hist = ticker_data.history(period="2y")
        df[name] = hist['Close']
    return df

data = get_data()

# Calcolo matematico dello Z-Score
mean = data.rolling(window=lookback).mean()
std = data.rolling(window=lookback).std()
z_score = (data - mean) / std

# Sezione 1: I dati di oggi
st.subheader("Termometro del Mercato (Ultima chiusura)")
st.write("Valori > 0 indicano un trend superiore alla media recente. Valori < 0 indicano debolezza.")

latest_z = z_score.dropna().iloc[-1]

# Creiamo 4 colonne per mostrare i numeri come in un cruscotto
col1, col2, col3, col4 = st.columns(4)
col1.metric("S&P 500", f"{latest_z['S&P 500 (Rischio)']:.2f}")
col2.metric("Oro", f"{latest_z['Oro (Rifugio)']:.2f}")
col3.metric("Rendimenti 10Y", f"{latest_z['Treasury 10Y (Rendimenti)']:.2f}")
col4.metric("VIX", f"{latest_z['VIX (Paura)']:.2f}")

# Sezione 2: Grafico interattivo
st.subheader("Evoluzione dello Z-Score nel tempo")
fig = px.line(z_score.dropna(), title="Compara i cicli di Rischio vs Paura")
st.plotly_chart(fig, use_container_width=True)

st.caption("Dati forniti da Yahoo Finance. Applicazione a scopo educativo.")
