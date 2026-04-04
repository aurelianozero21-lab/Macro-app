import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from fredapi import Fred

# Impostazioni della pagina
st.set_page_config(page_title="Macro Dashboard v3", layout="wide")
st.title("📊 Global Macro Dashboard (Prototipo v3)")

# --- RECUPERO DATI (Nascosto all'utente per pulizia) ---
@st.cache_data(ttl=3600)
def get_market_data():
    assets = {'S&P 500': '^GSPC', 'Oro': 'GC=F', 'Treasury 10Y': '^TNX', 'VIX': '^VIX'}
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="2y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
    return df.ffill().dropna()

@st.cache_data(ttl=3600)
def get_macro_data(api_key):
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y').tail(200).dropna()
    cpi = fred.get_series('CPIAUCSL').tail(60).dropna()
    inf = cpi.pct_change(periods=12) * 100
    return yc.iloc[-1], inf.iloc[-1]

# Scarichiamo i dati
market_data = get_market_data()
try:
    current_yc, current_inf = get_macro_data(st.secrets["FRED_API_KEY"])
except:
    current_yc, current_inf = 0, 0 # Fallback in caso di errore FRED

lookback = st.sidebar.slider("Giorni per Media Mobile (Z-Score)", 30, 200, 90)
z_score = ((market_data - market_data.rolling(window=lookback).mean()) / market_data.rolling(window=lookback).std()).dropna()
latest_z = z_score.iloc[-1] if not z_score.empty else None

# --- IL MOTORE DECISIONALE (SEMAFORO MACRO) ---
st.header("🚦 Semaforo del Business Cycle")

# Logica dell'algoritmo
fase = "Sconosciuta"
colore = "grey"
suggerimento = ""

if current_yc < 0:
    fase = "RALLENTAMENTO / RECESSIONE (Allarme Rosso)"
    colore = "red"
    suggerimento = "Difesa massima. Curva invertita. Sovrappesare Cash, Titoli di Stato a breve termine (2Y), Oro. Sottopesare Azionario e Crypto."
elif current_yc > 0 and latest_z['S&P 500'] < 0:
    fase = "RIPRESA (Inizio Ciclo)"
    colore = "orange"
    suggerimento = "La curva è normale ma il mercato è debole. Accumulo. Sovrappesare Bond a lunga scadenza, Azionario Tech, Bitcoin."
elif current_yc > 0 and latest_z['S&P 500'] > 0:
    fase = "ESPANSIONE (Risk-On)"
    colore = "green"
    suggerimento = "Crescita solida. Mercato in trend positivo. Sovrappesare Azionario globale, Commodities (Rame/Petrolio), Crypto. Sottopesare Bond."

# Creiamo un box colorato per l'output
st.markdown(f"""
<div style="padding: 20px; border-radius: 10px; background-color: {colore}; color: white; margin-bottom: 20px;">
    <h3 style="margin-top: 0;">Fase Attuale: {fase}</h3>
    <p style="font-size: 16px;"><strong>Allocazione Consigliata:</strong> {suggerimento}</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# --- SEZIONE DATI RAW ---
col_m1, col_m2 = st.columns(2)
col_m1.metric("Curva Rendimenti (10Y-2Y)", f"{current_yc:.2f} %", "Recession Warning!" if current_yc < 0 else "Normal", delta_color="inverse")
col_m2.metric("Inflazione USA (YoY)", f"{current_inf:.2f} %")

if latest_z is not None:
    st.subheader("Termometro di Borsa (Z-Score)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500", f"{latest_z['S&P 500']:.2f}")
    c2.metric("Oro", f"{latest_z['Oro']:.2f}")
    c3.metric("Rendimenti 10Y", f"{latest_z['Treasury 10Y']:.2f}")
    c4.metric("VIX", f"{latest_z['VIX']:.2f}")

    fig_z = px.line(z_score, title="Cicli di Rischio vs Paura")
    st.plotly_chart(fig_z, use_container_width=True)
