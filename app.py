import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred

st.set_page_config(page_title="Macro Dashboard v8", layout="wide")
st.title("📊 Global Macro Dashboard (Prototipo v8 - Sentiment & VIX)")

# --- LEGENDA E GLOSSARIO ---
with st.expander("📚 Clicca qui per leggere la Legenda e il Glossario dei termini"):
    st.markdown("""
    ### 📖 Glossario degli Indicatori
    * **Z-Score:** Un termometro statistico. Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva dei Rendimenti (T10Y2Y):** Se è **Invertita (< 0)**, gli investitori chiedono più interessi a breve termine per paura del futuro. È il miglior indicatore storico di recessione.
    * **DXY (Dollaro Index):** Se il Dollaro è molto forte, di solito fa scendere l'azionario, le crypto e le materie prime.
    * **Fase Risk-On / Risk-Off:** Nel *Risk-On* si comprano Azioni/Crypto; nel *Risk-Off* si comprano Oro, Franchi Svizzeri e Bond.
    * **VIX (Indice della Paura):** Misura la volatilità attesa sullo S&P 500. Valori alti = Panico (Spesso un'opportunità d'acquisto). Valori bassi = Compiacenza (Rischio di crollo).
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

# Nuova funzione per scaricare solo il VIX aggiornato
@st.cache_data(ttl=900) # Si aggiorna ogni 15 minuti
def get_vix_sentiment():
    vix = yf.Ticker('^VIX').history(period="1mo")['Close']
    return vix.iloc[-1] if not vix.empty else 20

lookback = st.sidebar.slider("Giorni per Media Mobile (Z-Score)", 30, 200, 90)

try:
    backtest_data, asset_names = load_and_backtest(st.secrets["FRED_API_KEY"], lookback)
    current_status = backtest_data.iloc[-1]
    current_vix = get_vix_sentiment()
except Exception as e:
    st.error(f"Errore nel caricamento dati. Dettaglio: {e}")
    st.stop()

# --- IL MOTORE DECISIONALE ---
st.header("🚦 Semaforo Macro (Trend di Medio Termine)")

if current_status['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
    colore = "#d32f2f"
    titolo = "🚨 FASE ATTUALE: RALLENTAMENTO / RECESSIONE"
    suggerimento = "Difesa massima. La curva dei rendimenti invertita segnala stress economico."
    settori = "🩺 Healthcare (XLV), ⚡ Utilities (XLU), 🛒 Beni di prima necessità (XLP)."
    valute = "🇨🇭 Franco Svizzero (CHF), 🇯🇵 Yen (JPY), 💵 Dollaro USA (USD)."
elif current_status['Fase_Macro'] == '2. Ripresa (Accumulo)':
    colore = "#f57c00"
    titolo = "🔋 FASE ATTUALE: RIPRESA ECONOMICA"
    suggerimento = "Fase ideale per accumulare a sconti. Curva normale ma mercati ancora spaventati."
    settori = "💻 Tecnologia (XLK), 🛍️ Consumi Discrezionali (XLY), 🏠 Real Estate (XLRE)."
    valute = "Accumulo graduale su 💶 Euro (EUR)."
else:
    colore = "#388e3c"
    titolo = "🚀 FASE ATTUALE: ESPANSIONE / RISK-ON"
    suggerimento = "Crescita solida. Spingere sull'acceleratore del rischio."
    settori = "🏭 Industriali (XLI), 🏦 Finanziari (XLF), 🛢️ Energia (XLE)."
    valute = "Valute Risk-On: 🇦🇺 Dollaro Australiano (AUD), 🇨🇦 Dollaro Canadese (CAD)."

st.markdown(f"""
<div style="padding: 25px; border-radius: 12px; background-color: {colore}; color: white; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h2 style="margin-top: 0; color: white;">{titolo}</h2>
    <p style="font-size: 18px;"><em>{suggerimento}</em></p>
    <ul style="font-size: 16px; line-height: 1.8;">
        <li><strong>🎯 Settori Azionari:</strong> {settori}</li>
        <li><strong>💱 Valute Forex:</strong> {valute}</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# --- NUOVA SEZIONE: SENTIMENT DI BREVE TERMINE ---
st.header("🧠 Sentiment di Breve Termine (Timing Operativo)")

col_text, col_gauge = st.columns([1, 1])

with col_text:
    st.write("Mentre il Semaforo Macro in alto ti dice **COSA** comprare, questo tachimetro ti suggerisce **QUANDO** entrare a mercato, misurando la psicologia di massa degli investitori tramite l'indice VIX.")
    
    if current_vix < 15:
        st.warning("⚠️ **Estrema Compiacenza (Avidità):** Il mercato è fin troppo tranquillo. Rischio elevato di correzioni improvvise. Evita di fare grossi acquisti in blocco ora.")
    elif 15 <= current_vix <= 25:
        st.info("⚖️ **Mercato Neutrale:** Volatilità nella norma. Segui tranquillamente le indicazioni del Semaforo Macro.")
    elif 25 < current_vix <= 35:
        st.success("😨 **Paura:** Iniziano i veri sconti. Ottimo momento per accumulare gli asset suggeriti dal Semaforo Macro.")
    else:
        st.error("🩸 **Panico Estremo (Buy the Blood!):** Crolli generalizzati. Storicamente i rendimenti migliori a 12 mesi si ottengono comprando in questi momenti di puro terrore.")

with col_gauge:
    fig_vix = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = current_vix,
        title = {'text': "Indice VIX (Paura)"},
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 50], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "black", 'thickness': 0.2},
            'bgcolor': "white",
            'steps': [
                {'range': [0, 15], 'color': "#81c784"},   # Verde (Compiacenza)
                {'range': [15, 25], 'color': "#fff176"},  # Giallo (Neutrale)
                {'range': [25, 35], 'color': "#ffb74d"},  # Arancione (Paura)
                {'range': [35, 50], 'color': "#e57373"}   # Rosso (Panico)
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': current_vix
            }
        }
    ))
    fig_vix.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_vix, use_container_width=True)

st.markdown("---")

# --- TERMOMETRO E BACKTEST ---
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
