import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from fredapi import Fred

# Impostazioni della pagina
st.set_page_config(page_title="Macro Dashboard v2", layout="wide")
st.title("📊 Global Macro Dashboard (Prototipo v2)")

# --- SEZIONE 1: DATI MACRO (FRED) ---
st.header("🌍 Motore Dati Macroeconomici (Economia Reale)")

try:
    # Colleghiamo la chiave segreta
    fred = Fred(api_key=st.secrets["FRED_API_KEY"])
    
    # Scarichiamo i dati storici (ultimi 5 anni per M2 e CPI, 2 anni per la curva)
    m2 = fred.get_series('M2SL').tail(60) 
    cpi = fred.get_series('CPIAUCSL').tail(60)
    yield_curve = fred.get_series('T10Y2Y').tail(500)
    
    # Calcoliamo l'inflazione anno su anno (YoY %)
    inflation_yoy = cpi.pct_change(periods=12) * 100
    
    # Mostriamo le metriche
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("M2 (Liquidità Globale)", f"{m2.dropna().iloc[-1]:,.0f} B$")
    col_m2.metric("Inflazione USA (YoY)", f"{inflation_yoy.dropna().iloc[-1]:.2f} %")
    
    # La curva dei rendimenti ha un colore condizionale (se < 0 è allerta)
    yc_val = yield_curve.dropna().iloc[-1]
    col_m3.metric("Curva Rendimenti (10Y-2Y)", f"{yc_val:.2f} %", 
                  delta="Invertita (Rischio!)" if yc_val < 0 else "Normale", 
                  delta_color="inverse")
    
    # Grafico della Liquidità
    st.subheader("Il Carburante dei Mercati: Liquidità M2")
    fig_m2 = px.line(m2.dropna(), title="Massa Monetaria USA (M2) in Miliardi di $")
    st.plotly_chart(fig_m2, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Errore con i dati FRED: Assicurati di aver inserito la FRED_API_KEY nei Secrets di Streamlit. Dettaglio: {e}")

st.markdown("---")

# --- SEZIONE 2: DATI DI MERCATO (YAHOO FINANCE) ---
st.header("📈 Termometro di Borsa (Z-Score)")

assets = {'S&P 500': '^GSPC', 'Oro': 'GC=F', 'Treasury 10Y': '^TNX', 'VIX': '^VIX'}
lookback = st.slider("Giorni per Media Mobile (Z-Score)", 30, 200, 90)

@st.cache_data(ttl=3600)
def get_data():
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="2y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
    return df.ffill().dropna()

data = get_data()

if not data.empty:
    z_score = ((data - data.rolling(window=lookback).mean()) / data.rolling(window=lookback).std()).dropna()
    
    if not z_score.empty:
        latest_z = z_score.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("S&P 500", f"{latest_z['S&P 500']:.2f}")
        c2.metric("Oro", f"{latest_z['Oro']:.2f}")
        c3.metric("Rendimenti 10Y", f"{latest_z['Treasury 10Y']:.2f}")
        c4.metric("VIX", f"{latest_z['VIX']:.2f}")

        fig_z = px.line(z_score, title="Cicli di Rischio vs Paura")
        st.plotly_chart(fig_z, use_container_width=True)
