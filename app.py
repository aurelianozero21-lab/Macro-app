import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred

st.set_page_config(page_title="Macro Dashboard v9", layout="wide")
st.title("📊 Global Macro & Crypto Dashboard (v9)")

# --- RECUPERO DATI ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
    # Asset Tradizionali + Crypto Base
    assets = {
        'S&P 500 (Azioni)': '^GSPC', 
        'Dollaro DXY (Forex)': 'DX-Y.NYB',
        'Oro (Rifugio)': 'GC=F',
        'Petrolio (Commodities)': 'CL=F',
        'Treasury 10Y (Bond)': '^TNX',
        'Bitcoin': 'BTC-USD',
        'Ethereum': 'ETH-USD'
    }
    
    df = pd.DataFrame()
    for name, ticker in assets.items():
        hist = yf.Ticker(ticker).history(period="15y")
        if not hist.empty:
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            df[name] = hist['Close']
            
    # Calcolo Metriche Crypto Avanzate
    df['Rapporto ETH/BTC'] = df['Ethereum'] / df['Bitcoin']
    
    # Dati FRED
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    
    df = df.ffill().dropna()
    
    # Calcolo Z-Score per tutti
    for col in df.columns:
        if col != 'YieldCurve':
            df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    df = df.dropna()
    
    # Motore Macro
    def assegna_fase(row):
        if row['YieldCurve'] < 0: return '1. Allarme Rosso (Recessione)'
        elif row['YieldCurve'] > 0 and row['Z_S&P 500 (Azioni)'] < 0: return '2. Ripresa (Accumulo)'
        else: return '3. Espansione (Risk-On)'
            
    df['Fase_Macro'] = df.apply(assegna_fase, axis=1)
    return df

@st.cache_data(ttl=900)
def get_vix():
    vix = yf.Ticker('^VIX').history(period="1mo")['Close']
    return vix.iloc[-1] if not vix.empty else 20

lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

try:
    df, vix_val = load_all_data(st.secrets["FRED_API_KEY"], lookback), get_vix()
    current = df.iloc[-1]
except Exception as e:
    st.error(f"Errore dati: {e}")
    st.stop()

# --- CREAZIONE DELLE SCHEDE (TABS) ---
tab1, tab2 = st.tabs(["🏛️ Macro & TradFi", "⚡ Crypto & Liquidity"])

# ==========================================
# SCHEDA 1: MACROECONOMIA TRADIZIONALE
# ==========================================
with tab1:
    st.header("🚦 Semaforo Macro (Trend di Medio Termine)")

    if current['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
        colore, titolo, sug = "#d32f2f", "🚨 RALLENTAMENTO / RECESSIONE", "Difesa massima. Curva invertita."
    elif current['Fase_Macro'] == '2. Ripresa (Accumulo)':
        colore, titolo, sug = "#f57c00", "🔋 RIPRESA ECONOMICA", "Fase ideale per accumulare a sconti. Curva normale ma mercati deboli."
    else:
        colore, titolo, sug = "#388e3c", "🚀 ESPANSIONE / RISK-ON", "Crescita solida. Spingere sull'acceleratore del rischio."

    st.markdown(f"""
    <div style="padding: 20px; border-radius: 10px; background-color: {colore}; color: white; margin-bottom: 20px;">
        <h3 style="margin-top: 0; color: white;">{titolo}</h3>
        <p><em>{sug}</em></p>
    </div>
    """, unsafe_allow_html=True)

    col_text, col_gauge = st.columns([1, 1])
    with col_text:
        st.write("**Sentiment di Breve Termine (VIX)**")
        if vix_val < 15: st.warning("⚠️ Compiacenza estrema. Rischio correzioni.")
        elif vix_val <= 25: st.info("⚖️ Neutrale. Segui il trend.")
        elif vix_val <= 35: st.success("😨 Paura. Iniziano gli sconti.")
        else: st.error("🩸 Panico! (Buy the Blood)")

    with col_gauge:
        fig_vix = go.Figure(go.Indicator(
            mode="gauge+number", value=vix_val, title={'text': "Indice VIX"},
            gauge={'axis': {'range': [0, 50]}, 'bar': {'color': "black"},
                   'steps': [{'range': [0, 15], 'color': "#81c784"}, {'range': [15, 25], 'color': "#fff176"},
                             {'range': [25, 35], 'color': "#ffb74d"}, {'range': [35, 50], 'color': "#e57373"}],
                   'threshold': {'line': {'color': "black", 'width': 4}, 'value': vix_val}}))
        fig_vix.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_vix, use_container_width=True)

    st.subheader("Termometro TradFi (Z-Score)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500", f"{current['Z_S&P 500 (Azioni)']:.2f}")
    c2.metric("Dollaro DXY", f"{current['Z_Dollaro DXY (Forex)']:.2f}")
    c3.metric("Oro", f"{current['Z_Oro (Rifugio)']:.2f}")
    c4.metric("Treasury 10Y", f"{current['Z_Treasury 10Y (Bond)']:.2f}")

# ==========================================
# SCHEDA 2: CRYPTO & LIQUIDITY
# ==========================================
with tab2:
    st.header("⚡ Ecosistema Crypto e Rischio")
    st.write("Questa sezione analizza la propensione al rischio nel mondo digitale. Bitcoin è la riserva di valore, Ethereum rappresenta la speculazione e la tecnologia (Altseason).")
    
    # Metriche Crypto
    c1, c2, c3 = st.columns(3)
    c1.metric("Z-Score Bitcoin", f"{current['Z_Bitcoin']:.2f}", 
              help="Forza di BTC rispetto alla sua media recente.")
    c2.metric("Z-Score Ethereum", f"{current['Z_Ethereum']:.2f}")
    
    # Analisi Rapporto ETH/BTC
    eth_btc_z = current['Z_Rapporto ETH/BTC']
    c3.metric("Propensione al Rischio Crypto (Z-Score ETH/BTC)", f"{eth_btc_z:.2f}", 
              delta="Risk-On (Altseason)" if eth_btc_z > 0 else "Risk-Off (Dominance BTC)")
    
    st.markdown("---")
    
    # Grafico Multiplo: BTC, ETH e Rapporto
    st.subheader("Dinamiche Interne del Mercato Crypto (Ultimo Anno)")
    fig_crypto = px.line(df.tail(252), y=['Z_Bitcoin', 'Z_Ethereum', 'Z_Rapporto ETH/BTC'], 
                         title="Z-Score: Bitcoin vs Ethereum vs Propensione al Rischio (ETH/BTC)")
    
    # Miglioriamo la grafica mettendo in evidenza il rapporto
    fig_crypto.update_traces(line=dict(width=3), selector=dict(name='Z_Rapporto ETH/BTC'))
    st.plotly_chart(fig_crypto, use_container_width=True)
    
    st.info("💡 **Come leggere il grafico:** Quando la linea del 'Rapporto ETH/BTC' sale forte (spesso insieme a un calo del Dollaro DXY), siamo in piena bolla speculativa (Altseason). Quando crolla, i capitali stanno scappando dalle Altcoin per rifugiarsi nella sicurezza di Bitcoin.")
