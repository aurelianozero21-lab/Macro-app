import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from fredapi import Fred

st.set_page_config(page_title="Macro Dashboard v5", layout="wide")
st.title("📊 Global Macro Dashboard (Prototipo v5 - Multi-Asset)")

# --- RECUPERO DATI E BACKTEST ---
@st.cache_data(ttl=3600)
def load_and_backtest(api_key, lookback):
    # Definiamo il paniere allargato di Asset Class
    assets = {
        'S&P 500 (Azioni)': '^GSPC', 
        'Bitcoin (Crypto)': 'BTC-USD',
        'Dollaro DXY (Forex)': 'DX-Y.NYB',
        'Oro (Rifugio)': 'GC=F',
        'Petrolio (Commodities)': 'CL=F',
        'Treasury 10Y (Bond)': '^TNX'
    }
    
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="15y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
    
    # Dati FRED per la Curva dei Rendimenti
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    
    df['YieldCurve'] = yc
    df = df.ffill().dropna() # Pulizia dei dati e fusi orari
    
    # Calcoliamo gli Z-Score per tutti gli asset
    for col in assets.keys():
        df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
        
    df = df.dropna()
    
    # Algoritmo decisionale
    def assegna_fase(row):
        if row['YieldCurve'] < 0:
            return '1. Allarme Rosso (Recessione)'
        elif row['YieldCurve'] > 0 and row['Z_S&P 500 (Azioni)'] < 0:
            return '2. Ripresa (Accumulo)'
        else:
            return '3. Espansione (Risk-On)'
            
    df['Fase_Macro'] = df.apply(assegna_fase, axis=1)
    # ECCO LA CORREZIONE QUI SOTTO: trasformiamo in lista standard
    return df, list(assets.keys())

lookback = st.sidebar.slider("Giorni per Media Mobile (Z-Score)", 30, 200, 90)

try:
    backtest_data, asset_names = load_and_backtest(st.secrets["FRED_API_KEY"], lookback)
    current_status = backtest_data.iloc[-1]
except Exception as e:
    st.error(f"Errore nel caricamento dati. Dettaglio: {e}")
    st.stop()

# --- IL MOTORE DECISIONALE OGGI ---
st.header("🚦 Semaforo Attuale e Allocazione")

if current_status['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
    colore, suggerimento = "red", "Difesa massima. Curva invertita. Sovrappesare Cash, Dollaro DXY, Bond Brevi, Oro. Sottopesare S&P 500, Petrolio e Bitcoin."
elif current_status['Fase_Macro'] == '2. Ripresa (Accumulo)':
    colore, suggerimento = "orange", "La curva è normale ma il mercato è debole. Fase di Accumulo. Iniziare a comprare Bitcoin e Azionario. Mantenere Bond."
else:
    colore, suggerimento = "green", "Crescita solida. Mercato in trend positivo. Sovrappesare S&P 500, Bitcoin, Petrolio. Sottopesare Dollaro e Bond."

st.markdown(f"""
<div style="padding: 20px; border-radius: 10px; background-color: {colore}; color: white; margin-bottom: 20px;">
    <h3 style="margin-top: 0;">Fase Attuale: {current_status['Fase_Macro']}</h3>
    <p style="font-size: 16px;"><strong>Allocazione Consigliata:</strong> {suggerimento}</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# --- TERMOMETRO MULTI-ASSET ---
st.header("🌡️ Termometro Multi-Asset (Z-Score Attuale)")
st.write("Valori > 0 indicano forza rispetto alla media, valori < 0 indicano debolezza a breve termine.")

col1, col2, col3 = st.columns(3)
col4, col5, col6 = st.columns(3)

cols = [col1, col2, col3, col4, col5, col6]
for i, asset in enumerate(asset_names):
    z_val = current_status[f'Z_{asset}']
    cols[i].metric(asset, f"{z_val:.2f}")

st.subheader("Analisi Intermarket: Rotazione degli Asset (Ultimo Anno)")
z_columns = [f'Z_{asset}' for asset in asset_names]
fig_z = px.line(backtest_data.tail(252), y=z_columns, title="Confronto della forza relativa tra le varie Asset Class")
st.plotly_chart(fig_z, use_container_width=True)

st.markdown("---")

# --- LA MACCHINA DEL TEMPO (BACKTEST VISIVO) ---
st.header("🔬 Backtest Storico (Ultimi 15 Anni)")
fig = px.scatter(
    backtest_data, 
    x=backtest_data.index, 
    y='S&P 500 (Azioni)', 
    color='Fase_Macro',
    color_discrete_map={
        '1. Allarme Rosso (Recessione)': 'red',
        '2. Ripresa (Accumulo)': 'orange',
        '3. Espansione (Risk-On)': 'green'
    },
    title="S&P 500 Colorato per Fase Macro"
)
fig.update_traces(marker=dict(size=4))
st.plotly_chart(fig, use_container_width=True)
