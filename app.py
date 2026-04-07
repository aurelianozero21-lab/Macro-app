import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
from io import BytesIO

# Importa tutta la logica dal file engine.py
from engine import *

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Macro Dashboard Pro", page_icon="📊", layout="wide")
st.title("📊 Global Macro, Crypto & AI Terminal")

with st.expander("📚 Cruscotto Rapido (Come leggere i dati)"):
    st.markdown("""
    * **Liquidità FED:** Quantità di moneta nel sistema. Se sale, i mercati salgono. Se scende, c'è rischio crollo.
    * **Shiller P/E (CAPE):** Valutazione storica. Se > 30, le azioni sono estremamente costose (Rischio Bolla).
    * **Stagionalità:** Compara l'anno in corso con la media storica. Aiuta a prevedere i periodi "caldi" o "freddi" dell'anno.
    * **Hash Ribbon (On-Chain):** Monitora i minatori di Bitcoin. La "Capitolazione" segna spesso il fondo del mercato.
    * **Smart Money (HYG):** Se le azioni salgono ma l'HYG scende, le banche stanno scaricando rischio di nascosto.
    * **Mayer Multiple (Crypto):** < 1.0 = Zona di Accumulo Storica. > 2.4 = Bolla Speculativa Estrema.
    """)

# --- INIZIALIZZAZIONE E SINCRONIZZAZIONE DATI ---
lookback = st.sidebar.slider("Giorni Media Mobile (Z-Score)", 30, 200, 90)

with st.spinner("📊 Sincronizzazione Dati Live e Motori FED..."):
    try:
        df = load_all_data(st.secrets["FRED_API_KEY"], lookback)
        live_prices = get_live_prices()
        hash_status, df_hash = get_onchain_metrics()
        df_etfs = get_etf_screener()
        df_crypto = get_crypto_screener()
        fgi_val, fgi_class = get_crypto_fgi()
        tension_index, top_news, region_scores = analyze_geopolitics()
        current = df.iloc[-1] if not df.empty else pd.Series()
        supabase_client = init_supabase()
    except Exception as e:
        st.error(f"Errore di connessione ai fornitori dati: {e}")
        st.stop()

if current.empty:
    st.error("Dati storici non disponibili. Riprova tra qualche minuto.")
    st.stop()

# --- CALCOLO STAGIONALITA' ---
df_sp500_corrente, df_sp500_storico = calcola_stagionalita(df, 'S&P 500')
df_btc_corrente, df_btc_storico = calcola_stagionalita(df, 'Bitcoin')

# --- SMART ALERTS (SISTEMA DI ALLARME ISTITUZIONALE) ---
alerts = check_smart_alerts(df, live_prices, tension_index, hash_status)
if alerts:
    st.markdown("---")
    for alert in alerts:
        if "BUY SIGNAL" in alert or "🚀" in alert or "🟢" in alert:
            st.success(f"**{alert}**")
        else:
            st.error(f"**{alert}**")
    st.markdown("---")

# Calcolo fase macro per l'AI
fase_attuale = calcola_fase_avanzata(current.get('YieldCurve', 0), current.get('Z_S&P 500', 0), tension_index)
ai_context = f"Fase Macro: {fase_attuale}, S&P500 Z-Score: {current.get('Z_S&P 500', 0):.2f}, Shiller CAPE: {current.get('CAPE', 0):.2f}, Liquidità FED Delta 30g: {current.get('Liquidity_Delta_30d', 0):.2f}T, Oro Z-Score: {current.get('Z_Oro', 0):.2f}, BTC Mayer: {current.get('Mayer_BTC', 0):.2f}, On-Chain BTC: {hash_status}."

# --- SIDEBAR: FUNZIONI PRO ---
st.sidebar.markdown("---")
def to_excel(dataframe):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    dataframe.to_excel(writer, index=True, sheet_name='Dati_Macro')
    writer.close()
    return output.getvalue()
st.sidebar.download_button("📥 Esporta Dati (Excel)", data=to_excel(df), file_name="macro_data.xlsx", mime="application/vnd.ms-excel")

st.sidebar.markdown("---")
st.sidebar.subheader("🗞️ Generatore Report AI")
if "morning_brief" not in st.session_state: st.session_state.morning_brief = ""

if st.sidebar.button("🤖 Genera Morning Briefing", use_container_width=True):
    if "GEMINI_API_KEY" in st.secrets:
        with st.sidebar.status("Elaborazione istituzionale in corso..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            mod = next((m.name for m in genai.list_models() if "flash" in m.name.lower() or "pro" in m.name.lower()), "gemini-1.5-flash")
            st.session_state.morning_brief = genai.GenerativeModel(mod).generate_content(f"Sei il Chief Investment Officer. Scrivi un report strategico mattutino basato su: {ai_context}. Usa il Markdown.").text
    else: st.sidebar.error("Chiave GEMINI mancante nei Secrets.")

if st.session_state.morning_brief:
    with st.sidebar.expander("📄 Leggi il Report", expanded=True):
        st.markdown(st.session_state.morning_brief)

st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Automazione Notifiche")
url_id = st.query_params.get("id", "")
bot_link = get_telegram_link()

st.sidebar.markdown(f"""
<a href="{bot_link}" target="_blank" style="text-decoration:none;">
    <button style="width:100%; border-radius:5px; background-color:#24A1DE; color:white; border:none; padding:10px; cursor:pointer; font-weight:bold;">
        🚀 Attiva Bot Telegram
    </button>
</a>
""", unsafe_allow_html=True)

tg_user_id = st.sidebar.text_input("ID Telegram (se manuale):", value=url_id)
if st.sidebar.button("💾 Salva ID nel Database", use_container_width=True):
    if tg_user_id and supabase_client:
        try:
            supabase_client.table("telegram_users").insert({"chat_id": str(tg_user_id)}).execute()
            st.sidebar.success("✅ Sincronizzazione Database completata!")
            st.query_params.clear()
        except Exception as e:
            if "duplicate key" in str(e).lower(): st.sidebar.info("✅ ID già presente nel sistema.")
            else: st.sidebar.error("Errore DB Supabase.")

# --- SCHEDE PRINCIPALI DELL'APPLICAZIONE ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏛️ Macro & Liquidity", "⚡ Crypto & On-Chain", "🌍 Geopolitica", "🔥 Risk Manager", "🤖 Quant Chat", "📚 Academy"])

# --- TAB 1: MACROECONOMIA E LIQUIDITA' ---
with tab1:
    st.header("🚦 Semaforo Macro Intelligente")
    if "1." in fase_attuale: st.error(f"🚨 **FASE DI MERCATO: {fase_attuale}**")
    elif "2." in fase_attuale: st.warning(f"⚖️ **FASE DI MERCATO: {fase_attuale}**")
    else: st.success(f"🚀 **FASE DI MERCATO: {fase_attuale}**")
    
    col_live1, col_live2, col_live3, col_live4 = st.columns(4)
    sp500_live = live_prices.get('^GSPC', current.get('S&P 500', 0))
    vix_live = live_prices.get('^VIX', current.get('VIX', 0))
    liq_delta = current.get('Liquidity_Delta_30d', 0)
    cape_val = current.get('CAPE', 0)
    
    col_live1.metric("S&P 500 (Live)", f"{sp500_live:,.2f}", delta=f"Z-Score: {current.get('Z_S&P 500', 0):.2f}")
    col_live2.metric("Liquidità FED Netta", f"${current.get('Fed_Liquidity_T', 0):.2f}T", delta=f"{'+' if liq_delta > 0 else ''}{liq_delta:.2f}T (30g)", delta_color="normal")
    col_live3.metric("Shiller P/E (CAPE)", f"{cape_val:.2f}", delta="> 30 Rischio Bolla", delta_color="inverse" if cape_val > 30 else "normal")
    col_live4.metric("VIX Index (Paura)", f"{vix_live:.2f}", delta="Volatilità", delta_color="off")
    
    st.markdown("---")
    st.header("📅 Cicli e Stagionalità (S&P 500)")
    st.write("Confronto tra l'anno in corso e la media storica degli ultimi 20 anni. Permette di capire se il mercato è in anticipo o in ritardo rispetto ai suoi normali flussi di capitale stagionali.")
    
    if not df_sp500_corrente.empty and not df_sp500_storico.empty:
        fig_season = go.Figure()
        anno_ora = pd.Timestamp.now().year
        fig_season.add_trace(go.Scatter(x=df_sp500_corrente['DayOfYear'], y=df_sp500_corrente['Cumulative'], name=f'S&P 500 ({anno_ora})', line=dict(color='#00b894', width=3)))
        fig_season.add_trace(go.Scatter(x=df_sp500_storico['DayOfYear'], y=df_sp500_storico['Cumulative Storico'], name='Media Storica (20 anni)', line=dict(color='#b2bec3', width=2, dash='dash')))
        fig_season.update_layout(height=400, xaxis_title="Giorno dell'Anno (1-365)", yaxis_title="Performance Cumulata (Base 100)", margin=dict(l=0, r=0, t=10, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)'))
        st.plotly_chart(fig_season, use_container_width=True)

    st.markdown("---")
    st.header("🌊 Fed Liquidity Tracker")
    st.write("Analisi di correlazione tra stampa di moneta (FED) e S&P 500.")
    
    if 'Fed_Liquidity_T' in df.columns and 'S&P 500' in df.columns:
        fig_liq = go.Figure()
        fig_liq.add_trace(go.Scatter(x=df.index, y=df['S&P 500'], name='S&P 500', yaxis='y1', line=dict(color='#00b894', width=2)))
        fig_liq.add_trace(go.Scatter(x=df.index, y=df['Fed_Liquidity_T'], name='Net Liquidity ($T)', yaxis='y2', line=dict(color='#0984e3', width=2)))
        fig_liq.update_layout(
            yaxis=dict(title='S&P 500 (Punti)', side='left', showgrid=False),
            yaxis2=dict(title='Liquidità FED ($ Trilioni)', side='right', overlaying='y', showgrid=False),
            height=380, margin=dict(l=0, r=0, t=30, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)')
        )
        st.plotly_chart(fig_liq, use_container_width=True)

    st.markdown("---")
    st.header("👁️ Smart Money & Divergenze")
    col_sm1, col_sm2 = st.columns(2)
    with col_sm1:
        st.subheader("🏦 Mercato del Credito (HYG)")
        if current.get('Z_S&P 500', 0) > 0 and current.get('Z_High Yield', 0) < 0: st.error("⚠️ **DIVERGENZA RIBASSISTA:** Le banche vendono rischio.")
        elif current.get('Z_S&P 500', 0) < 0 and current.get('Z_High Yield', 0) > 0: st.success("🟢 **DIVERGENZA RIALZISTA:** Lo Smart Money sta accumulando.")
        else: st.info("⚖️ **CONVERGENZA:** Mercato azionario e credito sono allineati.")
    with col_sm2:
        st.subheader("🖨️ Direzione Liquidità")
        if liq_delta > 0: st.success("🟢 **ESPANSIONE (Risk-On):** Il sistema è supportato dalla liquidità.")
        else: st.error("🔴 **CONTRAZIONE (Risk-Off):** La FED drena dollari. Rischio di correzione.")

    if not df_etfs.empty:
        st.markdown("---")
        st.header("🗺️ Screener Settoriale & ETF")
        col_g1, col_g2 = st.columns(2)
        with col_g1: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Geografia'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Aree Geografiche").update_layout(coloraxis_showscale=False, height=350), use_container_width=True)
        with col_g2: st.plotly_chart(px.bar(df_etfs[df_etfs['Categoria']=='Settore'], x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn', title="Settori S&P 500").update_layout(coloraxis_showscale=False, height=350), use_container_width=True)
        st.dataframe(df_etfs[['Asset', 'Categoria', 'Prezzo ($)', 'Perf. 1 Mese (%)', 'Segnale Operativo']].sort_values(by='Perf. 1 Mese (%)', ascending=False), use_container_width=True, hide_index=True)

# --- TAB 2: CRYPTO E ON-CHAIN ---
with tab2:
    st.header("⚡ Valutazione Ciclo Bitcoin")
    mayer_btc = current.get('Mayer_BTC', 0)
    col_pre1, col_pre2 = st.columns(2)
    with col_pre1:
        st.subheader("Fase Macro (Mayer Multiple)")
        if mayer_btc < 1.0: st.success("🔋 **ACCUMULO (Sconto Storico)**")
        elif mayer_btc < 2.0: st.warning("📈 **BULL MARKET (Trend Sano)**")
        else: st.error("💥 **BOLLA SPECULATIVA (Prendere Profitti)**")
    with col_pre2:
        st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=fgi_val, title={'text': f"Fear & Greed Index: {fgi_class}"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 45], 'color': "#e57373"}, {'range': [55, 100], 'color': "#81c784"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    btc_live = live_prices.get('BTC-USD', current.get('Bitcoin', 0))
    c1.metric("Prezzo BTC (Live)", f"${btc_live:,.0f}")
    c2.metric("Mayer Multiple", f"{mayer_btc:.2f}")
    c3.metric("RSI (14 Giorni)", f"{current.get('RSI_BTC', 0):.0f}")
    c4.metric("Distanza da ATH", f"{current.get('BTC_Drawdown', 0):.1f}%")
    
    st.markdown("---")
    st.header("📅 Stagionalità (Bitcoin)")
    st.write("L'andamento di Bitcoin nel corso dell'anno attuale rispetto alla media storica decennale.")
    if not df_btc_corrente.empty and not df_btc_storico.empty:
        fig_btc_season = go.Figure()
        anno_ora_btc = pd.Timestamp.now().year
        fig_btc_season.add_trace(go.Scatter(x=df_btc_corrente['DayOfYear'], y=df_btc_corrente['Cumulative'], name=f'Bitcoin ({anno_ora_btc})', line=dict(color='#fdcb6e', width=3)))
        fig_btc_season.add_trace(go.Scatter(x=df_btc_storico['DayOfYear'], y=df_btc_storico['Cumulative Storico'], name='Media Storica', line=dict(color='#b2bec3', width=2, dash='dash')))
        fig_btc_season.update_layout(height=400, xaxis_title="Giorno dell'Anno (1-365)", yaxis_title="Performance Cumulata (Base 100)", margin=dict(l=0, r=0, t=10, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)'))
        st.plotly_chart(fig_btc_season, use_container_width=True)

    st.markdown("---")
    st.header("⛓️ Analisi On-Chain: Hash Ribbon")
    st.write("Misura la salute della rete Bitcoin e la redditività dei Minatori. Quando la media veloce scende sotto la lenta, i minatori stanno capitolando (ottimo setup di lungo termine).")
    
    if "CAPITULATION" in hash_status:
        st.error(f"**Stato Rete Attuale:** {hash_status}")
    elif "BUY SIGNAL" in hash_status:
        st.success(f"**Stato Rete Attuale:** {hash_status}")
    else:
        st.info(f"**Stato Rete Attuale:** {hash_status}")
        
    if not df_hash.empty:
        fig_hash = go.Figure()
        fig_hash.add_trace(go.Scatter(x=df_hash.index, y=df_hash['SMA30'], name='SMA 30 (Veloce)', line=dict(color='#ff7675', width=2)))
        fig_hash.add_trace(go.Scatter(x=df_hash.index, y=df_hash['SMA60'], name='SMA 60 (Lenta)', line=dict(color='#0984e3', width=2)))
        fig_hash.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)'), yaxis_title="Terahashes/s")
        st.plotly_chart(fig_hash, use_container_width=True)
    
    if not df_crypto.empty: 
        st.markdown("---")
        st.subheader("Screener Altcoin (Rotazione 1M)")
        st.plotly_chart(px.bar(df_crypto, x='Asset', y='Perf. 1 Mese (%)', color='Perf. 1 Mese (%)', color_continuous_scale='RdYlGn').update_layout(coloraxis_showscale=False, height=350), use_container_width=True)

# --- TAB 3: GEOPOLITICA E MATERIE PRIME ---
with tab3:
    st.header("🌍 Radar Geopolitico e Rischio Globale")
    col_g1, col_g2, col_g3 = st.columns([1.5, 1, 1.2])
    with col_g1: 
        st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=tension_index, title={'text': "Tensione Globale (NLP AI)"}, gauge={'axis': {'range': [0, 100]}, 'steps': [{'range': [0, 40], 'color': "#81c784"}, {'range': [40, 60], 'color': "#ffb74d"}, {'range': [60, 100], 'color': "#e57373"}]})).update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)
    with col_g2:
        st.subheader("🗺️ Mappa Focolai")
        for region, count in region_scores.items(): st.metric(region, f"{count} Alert Stampa", delta="🔥 Tensione Alta" if count >= 2 else "Calmo", delta_color="inverse" if count >= 2 else "normal")
    with col_g3:
        st.subheader("🛢️ Beni Rifugio Live")
        gold_live = live_prices.get('GC=F', current.get('Oro', 0))
        oil_live = live_prices.get('CL=F', 0.0)
        z_oro = current.get('Z_Oro', 0)
        st.metric("Oro / Oncia", f"${gold_live:,.1f}", delta=f"Z-Score Trend: {z_oro:.2f}", delta_color="inverse" if z_oro > 1 else "normal")
        st.metric("Petrolio WTI / Barile", f"${oil_live:,.2f}", delta="Termometro Inflazione", delta_color="off")

    if top_news:
        st.markdown("---")
        st.subheader("📰 Ultime Notizie Analizzate")
        for item in top_news: st.markdown(f"- **[{'🔴 Rischio' if item['score'] > 0 else '🟢 Distensione'}]** [{item['titolo']}]({item['link']})")

# --- TAB 4: STRESS TEST E BACKTEST ---
with tab4:
    st.header("🔥 Risk Manager & Backtest Matematico")
    st.write("Inserisci l'allocazione del tuo capitale. Il motore simulerà le performance storiche a partire da 10.000$.")
    
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1: alloc_azioni = st.number_input("Azioni / ETF (%)", min_value=0, max_value=100, value=50)
    with col_p2: alloc_obbligazioni = st.number_input("Bonds (%)", min_value=0, max_value=100, value=20)
    with col_p3: alloc_crypto = st.number_input("Crypto (%)", min_value=0, max_value=100, value=10)
    with col_p4: alloc_difesa = st.number_input("Oro / Cash (%)", min_value=0, max_value=100, value=20)
    
    totale = alloc_azioni + alloc_obbligazioni + alloc_crypto + alloc_difesa
    if totale != 100:
        st.warning(f"⚠️ Attenzione: Il totale dell'allocazione è {totale}%. Modifica i valori per arrivare a 100%.")
    else:
        st.markdown("---")
        st.subheader("📈 Analisi Storica (Equity Curve)")
        
        pesi_utente = {
            'Azioni': alloc_azioni / 100.0,
            'Bonds': alloc_obbligazioni / 100.0,
            'Crypto': alloc_crypto / 100.0,
            'Difesa': alloc_difesa / 100.0
        }
        
        try:
            equity_portafoglio, equity_sp500, cagr, max_dd = calcola_backtest(df, pesi_utente)
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Valore Capitale Finale", f"${equity_portafoglio.iloc[-1]:,.2f}")
            col_m2.metric("Rendimento Medio Annuo (CAGR)", f"{cagr*100:.2f}%")
            col_m3.metric("Perdita Massima (Max Drawdown)", f"{max_dd*100:.2f}%", delta="Stress Storico", delta_color="inverse")
            
            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(x=equity_portafoglio.index, y=equity_portafoglio, name='Tuo Portafoglio', line=dict(color='#00b894', width=2)))
            fig_bt.add_trace(go.Scatter(x=equity_sp500.index, y=equity_sp500, name='S&P 500 (Benchmark)', line=dict(color='#b2bec3', width=1, dash='dash')))
            fig_bt.update_layout(height=400, yaxis_title="Capitale Accumulato ($)", margin=dict(l=0, r=0, t=10, b=0), legend=dict(x=0.01, y=0.99))
            st.plotly_chart(fig_bt, use_container_width=True)
        except Exception as e:
            st.error(f"Errore calcolo backtest: Assicurati di avere tutti i dati storici caricati ({e})")
    
    st.markdown("---")
    if st.button("🚀 Richiedi Valutazione Rischio AI", use_container_width=True):
        if "GEMINI_API_KEY" in st.secrets:
            with st.spinner("Modelli Quantitativi AI in calcolo..."):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                mod = next((m.name for m in genai.list_models() if "flash" in m.name.lower() or "pro" in m.name.lower()), "gemini-1.5-flash")
                st.markdown(genai.GenerativeModel(mod).generate_content(f"Agisci come un Risk Manager. Portafoglio: Azioni {alloc_azioni}%, Bond {alloc_obbligazioni}%, Crypto {alloc_crypto}%, Difesa {alloc_difesa}%. Macro attuale: {ai_context}. Fornisci vulnerabilità e ottimizzazioni in Markdown.").text)
        else: st.error("Manca GEMINI_API_KEY nei Secrets.")

# --- TAB 5: AI CHATBOT ---
with tab5:
    st.header("🤖 Quant AI Assistant")
    st.write("Interroga l'intelligenza artificiale sui dati in tempo reale della dashboard.")
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        mod = next((m.name for m in genai.list_models() if "flash" in m.name.lower()), "gemini-1.5-flash")
        
        if "chat_history" not in st.session_state: st.session_state.chat_history = []
        for m in st.session_state.chat_history: st.chat_message(m["role"]).markdown(m["content"])
        
        if prompt := st.chat_input("Esempio: L'oro è sopravvalutato rispetto al rischio attuale?"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.chat_message("user").markdown(prompt)
            res = genai.GenerativeModel(mod).generate_content(f"Contesto Dati Live: {ai_context}\n\nDomanda dell'utente: {prompt}").text
            st.chat_message("assistant").markdown(res)
            st.session_state.chat_history.append({"role": "assistant", "content": res})

# --- TAB 6: ACADEMY ISTITUZIONALE ---
with tab6:
    st.header("📚 Macro Academy: Masterclass per Investitori")
    st.write("I principi matematici e logici alla base della piattaforma.")
    
    with st.expander("🌊 1. La Liquidità Netta FED (Il motore dei mercati)"):
        st.markdown("""**La Liquidità comanda, i fondamentali seguono.** La "Net Liquidity" si calcola come: `Bilancio FED - Conto del Tesoro (TGA) - Reverse Repo`. Quando sale, gonfia Azioni e Bitcoin. Se scende, la liquidità viene drenata e i mercati faticano.""")
    with st.expander("🏛️ 2. Shiller P/E (CAPE Ratio) - Rilevatore di Bolle"):
        st.markdown("""Creato dal Premio Nobel Robert Shiller, valuta se le azioni sono care dividendo il prezzo dell'S&P 500 per la media degli utili degli ultimi 10 anni (aggiustati per l'inflazione). Storicamente, un **CAPE > 30** indica un mercato in fortissima sopravvalutazione e ha preceduto i più grandi bear market (1929, 2000, 2021).""")
    with st.expander("📅 3. Stagionalità (Seasonality)"):
        st.markdown("""I mercati azionari e crypto non sono del tutto casuali, ma presentano pattern temporali ricorrenti (es. 'Sell in May and go away' o il Rally di Natale). Il grafico stagionale sovrappone il rendimento cumulato dell'anno in corso alla media matematica degli ultimi 20 anni. Se la linea verde si discosta troppo da quella tratteggiata, ci troviamo in un'anomalia statistica che tenderà, prima o poi, a ricongiungersi alla media ("mean reversion").""")
    with st.expander("📉 4. CAGR e Maximum Drawdown (Il vero Rischio)"): 
        st.markdown("""Il **CAGR** è la percentuale media di crescita annua del portafoglio. Il **Maximum Drawdown** è la perdita peggiore (dal picco al minimo). Serve a capire la tua tenuta emotiva durante i crash.""")
    with st.expander("📊 5. Lo Z-Score (La Misura dell'Eccesso)"): 
        st.markdown("""Lo Z-Score ci dice di quante *deviazioni standard* il prezzo si è allontanato dalla media a 90 giorni. > 2 = Rischio correzione immediata, < -2 = Ipervenduto.""")
    with st.expander("🏛️ 6. La Curva dei Rendimenti (L'Oracolo)"): 
        st.markdown("""Se i titoli a 2 anni pagano più di quelli a 10 anni (Curva < 0), significa che il mercato ha estrema paura del presente. Anticipa storicamente le recessioni.""")
    with st.expander("👁️ 7. Smart Money Divergence (HYG vs S&P)"): 
        st.markdown("""Se l'S&P 500 sale ma le obbligazioni High Yield (HYG) scendono, il "Retail" sta comprando per fomo mentre le Banche scaricano asset tossici in silenzio.""")
    with st.expander("₿ 8. Il Mayer Multiple (Bottom & Top Crypto)"): 
        st.markdown("""Prezzo BTC diviso la Media Mobile a 200 giorni. < 1.0 = Zona di forte accumulo; > 2.4 = Segnale matematico di euforia e presa di profitto.""")
    with st.expander("⛓️ 9. Hash Ribbon (Analisi On-Chain)"):
        st.markdown("""Guarda direttamente la potenza di calcolo della blockchain di Bitcoin (Hash Rate). Quando il prezzo scende troppo, i minatori meno efficienti spengono le macchine e vanno in 'Capitolazione' (SMA 30 scende sotto SMA 60). Quando la rete si riprende (SMA 30 incrocia al rialzo SMA 60), si genera storicamente uno dei segnali di acquisto più potenti e affidabili del mercato crypto.""")
