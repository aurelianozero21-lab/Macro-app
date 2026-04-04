import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from fredapi import Fred

st.set_page_config(page_title="Macro Dashboard v7", layout="wide")
st.title("📊 Global Macro Dashboard (Prototipo v7 - Legenda & UX)")

# --- LEGENDA E GLOSSARIO (Nuova Sezione) ---
with st.expander("📚 Clicca qui per leggere la Legenda e il Glossario dei termini"):
    st.markdown("""
    ### 📖 Glossario degli Indicatori
    * **Z-Score:** Un termometro statistico. Misura quanto un prezzo attuale si sta discostando dalla sua media storica recente. 
        * *Valore > 0:* L'asset è in un trend positivo (forte).
        * *Valore < 0:* L'asset è in un trend negativo (debole).
        * *Valore > +2 o < -2:* Fasi estreme (ipercomprato o ipervenduto).
    * **Curva dei Rendimenti (T10Y2Y):** È la differenza tra gli interessi pagati dai Titoli di Stato USA a 10 anni e quelli a 2 anni. 
        * *Normale (> 0):* L'economia è sana, chi presta soldi a lungo termine viene pagato di più.
        * *Invertita (< 0):* Anomalia grave. Gli investitori hanno talmente paura del futuro immediato che chiedono più interessi a breve termine. **È il miglior indicatore storico per prevedere una recessione.**
    * **DXY (Dollaro Index):** Misura la forza del Dollaro USA contro le altre monete globali. Un Dollaro molto forte drena liquidità dal mondo: di solito fa scendere l'azionario, le crypto e le materie prime (e viceversa).
    * **Fase Risk-On / Risk-Off:** * *Risk-On:* Gli investitori sono ottimisti, si prendono rischi comprando Azioni, Crypto e valute esotiche.
        * *Risk-Off:* Gli investitori hanno paura, si rifugiano in asset sicuri (Oro, Franchi Svizzeri, Titoli di Stato a breve termine, Dollaro).
    """)

# --- RECUPERO DATI E BACKTEST ---
@st.cache_data(ttl=3600)
def load_and_backtest(api_key, lookback):
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
    
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    
    df['YieldCurve'] = yc
    df = df.ffill().dropna()
    
    for col in assets.keys():
        df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
        
    df = df.dropna()
    
    def assegna_fase(row):
        if row['YieldCurve'] < 0:
            return '1. Allarme Rosso (Recessione)'
        elif row['YieldCurve'] > 0 and row['Z_S&P 500 (Azioni)'] < 0:
            return '2. Ripresa (Accumulo)'
        else:
            return '3. Espansione (Risk-On)'
            
    df['Fase_Macro'] = df.apply(assegna_fase, axis=1)
    return df, list(assets.keys())

lookback = st.sidebar.slider("Giorni per Media Mobile (Z-Score)", 30, 200, 90)

try:
    backtest_data, asset_names = load_and_backtest(st.secrets["FRED_API_KEY"], lookback)
    current_status = backtest_data.iloc[-1]
except Exception as e:
    st.error(f"Errore nel caricamento dati. Dettaglio: {e}")
    st.stop()

# --- IL MOTORE DECISIONALE ---
st.header("🚦 Semaforo Attuale e Allocazione Dettagliata")

if current_status['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
    colore = "#d32f2f"
    titolo = "🚨 FASE ATTUALE: RALLENTAMENTO / RECESSIONE"
    suggerimento = "Difesa massima. La curva dei rendimenti invertita segnala forte stress economico."
    settori = "🩺 **Healthcare (XLV)**, ⚡ **Utilities (XLU)**, 🛒 **Beni di prima necessità (XLP)**."
    valute = "🇨🇭 **Franco Svizzero (CHF)**, 🇯🇵 **Yen Giapponese (JPY)**, 💵 **Dollaro USA (USD)**."
elif current_status['Fase_Macro'] == '2. Ripresa (Accumulo)':
    colore = "#f57c00"
    titolo = "🔋 FASE ATTUALE: RIPRESA ECONOMICA"
    suggerimento = "La curva è normale ma i mercati sono deboli. Fase ideale per accumulare a sconti."
    settori = "💻 **Tecnologia (XLK)**, 🛍️ **Consumi Discrezionali (XLY)**, 🏠 **Real Estate (XLRE)**."
    valute = "Inizio indebolimento Dollaro. Accumulo graduale su 💶 **Euro (EUR)**."
else:
    colore = "#388e3c"
    titolo = "🚀 FASE ATTUALE: ESPANSIONE / RISK-ON"
    suggerimento = "Crescita solida. Mercato in trend positivo. Spingere sull'acceleratore del rischio."
    settori = "🏭 **Industriali (XLI)**, 🏦 **Finanziari (XLF)**, 🛢️ **Energia (XLE)**."
    valute = "Valute 'Risk-On' (esportatori): 🇦🇺 **Dollaro Australiano (AUD)**, 🇨🇦 **Dollaro Canadese (CAD)**."

st.markdown(f"""
<div style="padding: 25px; border-radius: 12px; background-color: {colore}; color: white; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h2 style="margin-top: 0; color: white;">{titolo}</h2>
    <p style="font-size: 18px;"><em>{suggerimento}</em></p>
    <hr style="border-top: 1px solid rgba(255,255,255,0.3);">
    <ul style="font-size: 16px; line-height: 1.8;">
        <li><strong>🎯 Settori Azionari:</strong> {settori}</li>
        <li><strong>💱 Valute Forex:</strong> {valute}</li>
    </ul>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

st.header("🌡️ Termometro Multi-Asset (Z-Score Attuale)")
col1, col2, col3 = st.columns(3)
col4, col5, col6 = st.columns(3)
cols = [col1, col2, col3, col4, col5, col6]
for i, asset in enumerate(asset_names):
    cols[i].metric(asset, f"{current_status[f'Z_{asset}']:.2f}")

st.subheader("Analisi Intermarket: Rotazione degli Asset (Ultimo Anno)")
z_columns = [f'Z_{asset}' for asset in asset_names]
fig_z = px.line(backtest_data.tail(252), y=z_columns, title="Confronto della forza relativa (Z-Score)")
st.plotly_chart(fig_z, use_container_width=True)

st.markdown("---")

st.header("🔬 Backtest Storico (Ultimi 15 Anni)")
fig = px.scatter(
    backtest_data, x=backtest_data.index, y='S&P 500 (Azioni)', color='Fase_Macro',
    color_discrete_map={'1. Allarme Rosso (Recessione)': 'red', '2. Ripresa (Accumulo)': 'orange', '3. Espansione (Risk-On)': 'green'},
    title="S&P 500 Colorato per Fase Macro"
)
fig.update_traces(marker=dict(size=4))
st.plotly_chart(fig, use_container_width=True)
