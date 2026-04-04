import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred

st.set_page_config(page_title="Macro Dashboard v10", layout="wide")
st.title("📊 Global Macro & Crypto Dashboard (v10)")

# --- LEGENDA E GLOSSARIO ---
with st.expander("📚 Clicca qui per leggere la Legenda e il Glossario dei termini"):
    st.markdown("""
    ### 📖 Glossario degli Indicatori
    * **Z-Score:** Un termometro statistico. Misura se un asset è in trend positivo (> 0) o negativo (< 0).
    * **Curva dei Rendimenti (T10Y2Y):** Se è **Invertita (< 0)** segnala recessione. Se torna **Normale (> 0)** dopo un'inversione, inizia la ripresa.
    * **VIX (Indice della Paura):** Valori alti = Panico (Opportunità). Valori bassi = Compiacenza (Pericolo).
    * **Rotazione Settoriale:** L'arte di spostare i soldi nei settori dell'economia che performano meglio in base alla fase in cui ci troviamo.
    """)

# --- RECUPERO DATI ---
@st.cache_data(ttl=3600)
def load_all_data(api_key, lookback):
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
            
    df['Rapporto ETH/BTC'] = df['Ethereum'] / df['Bitcoin']
    
    fred = Fred(api_key=api_key)
    yc = fred.get_series('T10Y2Y')
    yc.index = pd.to_datetime(yc.index)
    df['YieldCurve'] = yc
    
    df = df.ffill().dropna()
    
    for col in df.columns:
        if col != 'YieldCurve':
            df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    df = df.dropna()
    
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
    st.header("🚦 Semaforo Macro e Asset Allocation")

    if current['Fase_Macro'] == '1. Allarme Rosso (Recessione)':
        colore = "#d32f2f"
        titolo = "🚨 FASE ATTUALE: RALLENTAMENTO / RECESSIONE"
        sug = "Difesa massima. La curva invertita segnala stress economico imminente o in corso."
        settori = "🩺 **Healthcare (XLV)**, ⚡ **Utilities (XLU)**, 🛒 **Beni di prima necessità (XLP)**. Evita i ciclici."
        valute = "🇨🇭 **Franco Svizzero (CHF)**, 🇯🇵 **Yen (JPY)**, 💵 **Dollaro USA (USD)**."
        bond_comm = "📜 **Bond:** Breve scadenza (1-3 anni) per difendere il capitale. 🪨 **Commodities:** Solo Oro."
    elif current['Fase_Macro'] == '2. Ripresa (Accumulo)':
        colore = "#f57c00"
        titolo = "🔋 FASE ATTUALE: RIPRESA ECONOMICA"
        sug = "La curva è normale ma i mercati sono deboli. Fase ideale per accumulare asset di rischio a sconto."
        settori = "💻 **Tecnologia (XLK)**, 🛍️ **Consumi Discrezionali (XLY)**, 🏠 **Real Estate (XLRE)**."
        valute = "Inizio indebolimento Dollaro. Accumulo su 💶 **Euro (EUR)** e 💷 **Sterlina (GBP)**."
        bond_comm = "📜 **Bond:** Lunga scadenza (TLT) per sfruttare il taglio dei tassi. 🪨 **Commodities:** Rame e Argento."
    else:
        colore = "#388e3c"
        titolo = "🚀 FASE ATTUALE: ESPANSIONE / RISK-ON"
        sug = "Crescita solida. Mercato in trend positivo. Spingere sull'acceleratore del rischio."
        settori = "🏭 **Industriali (XLI)**, 🏦 **Finanziari (XLF)**, 🛢️ **Energia (XLE)**, 🏗️ **Materiali (XLB)**."
        valute = "Valute esportatrici: 🇦🇺 **Dollaro Australiano (AUD)**, 🇨🇦 **Dollaro Canadese (CAD)**."
        bond_comm = "📜 **Bond:** Sottopesare o usare High Yield (HYG). 🪨 **Commodities:** Petrolio e Rame."

    st.markdown(f"""
    <div style="padding: 25px; border-radius: 12px; background-color: {colore}; color: white; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="margin-top: 0; color: white;">{titolo}</h2>
        <p style="font-size: 18px;"><em>{sug}</em></p>
        <hr style="border-top: 1px solid rgba(255,255,255,0.3);">
        <ul style="font-size: 16px; line-height: 1.8;">
            <li><strong>🎯 Azionario (Settori):</strong> {settori}</li>
            <li><strong>💱 Forex (Valute):</strong> {valute}</li>
            <li><strong>⚖️ Bond & Commodities:</strong> {bond_comm}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    col_text, col_gauge = st.columns([1, 1])
    with col_text:
        st.write("### 🧠 Sentiment di Breve Termine (VIX)")
        if vix_val < 15: st.warning("⚠️ **Compiacenza estrema.** Mercato euforico, rischio prese di beneficio. Non entrare in blocco all-in.")
        elif vix_val <= 25: st.info("⚖️ **Neutrale.** Segui il trend della macroeconomia senza paura.")
        elif vix_val <= 35: st.success("😨 **Paura.** Iniziano i veri sconti. Accumula progressivamente.")
        else: st.error("🩸 **Panico! (Buy the Blood).** Disperazione sui mercati. Storicamente, il momento migliore per comprare.")

    with col_gauge:
        fig_vix = go.Figure(go.Indicator(
            mode="gauge+number", value=vix_val, title={'text': "Indice VIX"},
            gauge={'axis': {'range': [0, 50]}, 'bar': {'color': "black"},
                   'steps': [{'range': [0, 15], 'color': "#81c784"}, {'range': [15, 25], 'color': "#fff176"},
                             {'range': [25, 35], 'color': "#ffb74d"}, {'range': [35, 50], 'color': "#e57373"}],
                   'threshold': {'line': {'color': "black", 'width': 4}, 'value': vix_val}}))
        fig_vix.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_vix, use_container_width=True)

    st.markdown("---")
    st.subheader("🌡️ Termometro TradFi (Z-Score)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("S&P 500", f"{current['Z_S&P 500 (Azioni)']:.2f}")
    c2.metric("Dollaro DXY", f"{current['Z_Dollaro DXY (Forex)']:.2f}")
    c3.metric("Oro", f"{current['Z_Oro (Rifugio)']:.2f}")
    c4.metric("Treasury 10Y", f"{current['Z_Treasury 10Y (Bond)']:.2f}")

    st.subheader("🔬 Backtest Storico (Ultimi 15 Anni)")
    fig = px.scatter(
        df, x=df.index, y='S&P 500 (Azioni)', color='Fase_Macro',
        color_discrete_map={'1. Allarme Rosso (Recessione)': 'red', '2. Ripresa (Accumulo)': 'orange', '3. Espansione (Risk-On)': 'green'},
        title="S&P 500 Colorato per Fase Macro"
    )
    fig.update_traces(marker=dict(size=4))
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# SCHEDA 2: CRYPTO & LIQUIDITY
# ==========================================
with tab2:
    st.header("⚡ Ecosistema Crypto e Rischio")
    st.write("Questa sezione analizza la propensione al rischio nel mondo digitale. Bitcoin è la riserva di valore, Ethereum rappresenta la speculazione e la tecnologia (Altseason).")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Z-Score Bitcoin", f"{current['Z_Bitcoin']:.2f}")
    c2.metric("Z-Score Ethereum", f"{current['Z_Ethereum']:.2f}")
    
    eth_btc_z = current['Z_Rapporto ETH/BTC']
    c3.metric("Propensione al Rischio Crypto (ETH/BTC)", f"{eth_btc_z:.2f}", 
              delta="Risk-On (Altseason)" if eth_btc_z > 0 else "Risk-Off (Dominance BTC)")
    
    st.markdown("---")
    st.subheader("Dinamiche Interne del Mercato Crypto (Ultimo Anno)")
    fig_crypto = px.line(df.tail(252), y=['Z_Bitcoin', 'Z_Ethereum', 'Z_Rapporto ETH/BTC'], 
                         title="Z-Score: Bitcoin vs Ethereum vs Propensione al Rischio (ETH/BTC)")
    fig_crypto.update_traces(line=dict(width=3), selector=dict(name='Z_Rapporto ETH/BTC'))
    st.plotly_chart(fig_crypto, use_container_width=True)
