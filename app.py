import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from fredapi import Fred

st.set_page_config(page_title="Macro Dashboard v4", layout="wide")
st.title("📊 Global Macro Dashboard (Prototipo v4 - Backtest)")

# --- RECUPERO DATI E BACKTEST ---
@st.cache_data(ttl=3600)
def load_and_backtest(api_key, lookback):
    # 1. Scarichiamo 15 anni di S&P 500
    sp500 = yf.Ticker('^GSPC').history(period="15y")['Close']
    sp500.index = pd.to_datetime(sp500.index).tz_localize(None).normalize()
    
    # 2. Scarichiamo la Curva dei Rendimenti dalla FRED
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    
    # 3. Uniamo i dati nello stesso calendario
    df = pd.DataFrame({'SP500': sp500, 'YieldCurve': yc}).dropna()
    
    # 4. Calcoliamo lo Z-Score Storico
    df['Z_Score'] = (df['SP500'] - df['SP500'].rolling(window=lookback).mean()) / df['SP500'].rolling(window=lookback).std()
    df = df.dropna()
    
    # 5. Applichiamo l'algoritmo al passato (La Macchina del Tempo)
    def assegna_fase(row):
        if row['YieldCurve'] < 0:
            return '1. Allarme Rosso (Recessione)'
        elif row['YieldCurve'] > 0 and row['Z_Score'] < 0:
            return '2. Ripresa (Accumulo)'
        else:
            return '3. Espansione (Risk-On)'
            
    df['Fase_Macro'] = df.apply(assegna_fase, axis=1)
    return df

# Recuperiamo i dati
lookback = st.sidebar.slider("Giorni per Media Mobile (Z-Score)", 30, 200, 90)

try:
    backtest_data = load_and_backtest(st.secrets["FRED_API_KEY"], lookback)
    current_status = backtest_data.iloc[-1]
except Exception as e:
    st.error(f"Errore nel caricamento dati: {e}")
    st.stop()

# --- IL MOTORE DECISIONALE OGGI ---
st.header("🚦 Semaforo Attuale")

if current_status['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
    colore, suggerimento = "red", "Difesa massima. Curva invertita. Sovrappesare Cash, Bond Brevi (2Y), Oro. Sottopesare Azionario."
elif current_status['Fase_Macro'] == '2. Ripresa (Accumulo)':
    colore, suggerimento = "orange", "La curva è normale ma il mercato è debole. Accumulo. Sovrappesare Bond Lunghi, Azionario Tech."
else:
    colore, suggerimento = "green", "Crescita solida. Mercato in trend positivo. Sovrappesare Azionario, Commodities."

st.markdown(f"""
<div style="padding: 20px; border-radius: 10px; background-color: {colore}; color: white; margin-bottom: 20px;">
    <h3 style="margin-top: 0;">Fase Attuale: {current_status['Fase_Macro']}</h3>
    <p style="font-size: 16px;"><strong>Allocazione Consigliata:</strong> {suggerimento}</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# --- LA MACCHINA DEL TEMPO (BACKTEST VISIVO) ---
st.header("🔬 Backtest Storico (Ultimi 15 Anni)")
st.write("Questo grafico mostra l'andamento dello S&P 500. I colori rappresentano le fasi del ciclo macroeconomico calcolate dall'algoritmo nel passato.")

# Creiamo il grafico a dispersione colorato per fase
fig = px.scatter(
    backtest_data, 
    x=backtest_data.index, 
    y='SP500', 
    color='Fase_Macro',
    color_discrete_map={
        '1. Allarme Rosso (Recessione)': 'red',
        '2. Ripresa (Accumulo)': 'orange',
        '3. Espansione (Risk-On)': 'green'
    },
    title="S&P 500 Colorato per Fase Macro (Curva Rendimenti + Z-Score)"
)
fig.update_traces(marker=dict(size=4)) # Rimpiccioliamo i pallini per vederli meglio come linea
st.plotly_chart(fig, use_container_width=True)

st.caption("Nota metodologica: Questo backtest non include i costi di transazione e utilizza dati 'Point in time' sincronizzati. A scopo puramente educativo.")
