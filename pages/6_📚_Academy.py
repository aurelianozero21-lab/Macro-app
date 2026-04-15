import streamlit as st

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Quant Academy", page_icon="📚", layout="wide")

st.title("📚 Quant Academy: Masterclass Istituzionale")
st.write("I principi matematici e le logiche di mercato che alimentano l'intelligenza di questa piattaforma. Nessuna magia, solo statistica applicata.")

st.markdown("---")

# Divisione in sottomoduli per non appesantire la lettura
mod_macro, mod_risk, mod_crypto = st.tabs([
    "🏛️ Modulo 1: I Motori Macroeconomici", 
    "⚖️ Modulo 2: Valutazione & Rischio", 
    "⛓️ Modulo 3: Dinamiche On-Chain"
])

# ==========================================
# MODULO 1: MACROECONOMIA
# ==========================================
with mod_macro:
    st.header("🌊 La Liquidità Netta della FED")
    st.write("Nel mercato moderno, i fondamentali delle aziende contano meno della quantità di denaro in circolazione. La regola d'oro è: **se la liquidità sale, gli asset a rischio (Azioni, Crypto) salgono.**")
    
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.info("**La Formula (Dietro le quinte):**\n\n`Totale Bilancio FED` \n- `Conto del Tesoro (TGA)` \n- `Reverse Repo (RRP)` \n= **Liquidità Netta**")
    with col_l2:
        st.write("**Esempio Storico:** Nel 2020 la FED ha stampato trilioni (Liquidità 🚀) e i mercati hanno fatto i massimi storici. Nel 2022 ha iniziato a drenare liquidità (Quantitative Tightening) e i mercati sono crollati.")
    
    st.markdown("---")
    
    st.header("☠️ L'Inversione della Curva dei Rendimenti (T10Y2Y)")
    st.write("È considerato l'indicatore recessivo più affidabile della storia finanziaria. Misura la differenza di rendimento tra i Titoli di Stato USA a 10 anni e quelli a 2 anni.")
    
    c_y1, c_y2, c_y3 = st.columns(3)
    c_y1.success("**Curva Normale (> 0)**\n\nI bond a 10 anni pagano più di quelli a 2. L'economia è sana e gli investitori sono ottimisti sul futuro.")
    c_y2.error("**Curva Invertita (< 0)**\n\nI bond a 2 anni pagano PIÙ dei decennali. Il mercato ha il terrore del presente. Segna l'arrivo di una recessione.")
    c_y3.warning("**Re-Steepening**\n\nLa curva torna positiva dopo un'inversione. Spesso è il momento esatto in cui i mercati azionari crollano (perché la FED taglia i tassi in preda al panico).")

# ==========================================
# MODULO 2: VALUTAZIONE E RISCHIO
# ==========================================
with mod_risk:
    st.header("🏛️ Lo Shiller P/E (CAPE Ratio)")
    st.write("Ideato dal Premio Nobel Robert Shiller, serve a capire se l'intero mercato azionario (S&P 500) è economico o in bolla. Divide il prezzo del mercato per la media degli utili degli ultimi 10 anni (aggiustati per l'inflazione).")
    
    st.markdown("""
    | Valore CAPE | Significato Storico | Cosa fare statisticamente? |
    | :--- | :--- | :--- |
    | **Sotto 15** | Sottovalutazione Estrema (Es: Bottom 2009) | Accumulo aggressivo di azioni |
    | **15 - 25** | Valutazione Equa (Fair Value) | Mantenere il piano di accumulo |
    | **25 - 30** | Sopravvalutazione | Iniziare a coprirsi con Bond/Oro |
    | **Sopra 30** | **Bolla Speculativa** (Es: Dot-Com 2000) | Ridurre drasticamente l'esposizione |
    """)
    
    st.markdown("---")
    
    st.header("👁️ Smart Money Divergence (Azioni vs HYG)")
    st.write("I mercati obbligazionari (Bond) sono scambiati da professionisti e istituzioni, il mercato azionario è pieno di investitori retail (amatoriali). L'HYG è l'ETF delle obbligazioni 'High Yield' (ad alto rischio).")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.error("**La Trappola (Divergenza Ribassista)**\n\nL'S&P 500 sale (nuovi massimi), ma l'HYG scende. Significa che il parco buoi sta comprando azioni per euforia, ma le Banche stanno vendendo i loro asset a rischio in silenzio. Il crollo è vicino.")
    with col_d2:
        st.success("**Il Segnale Nascosto (Divergenza Rialzista)**\n\nL'S&P 500 scende, ma l'HYG inizia a salire. I media urlano al disastro, ma le grandi istituzioni stanno già ricomprando a piene mani. Ottimo momento per entrare.")

# ==========================================
# MODULO 3: ON-CHAIN & CRYPTO
# ==========================================
with mod_crypto:
    st.header("⛓️ Hash Ribbon (La Capitolazione dei Minatori)")
    st.write("Un indicatore che legge direttamente la Blockchain (l'Hash Rate). I Minatori hanno costi enormi (elettricità, hardware). Quando il prezzo di Bitcoin scende troppo, vanno in perdita e spengono i macchinari, creando una 'Capitolazione'.")
    
    st.info("**Come si legge:** Il motore calcola la Media Mobile a 30 giorni (Veloce) e a 60 giorni (Lenta) della potenza di calcolo della rete.")
    
    c_hr1, c_hr2, c_hr3 = st.columns(3)
    c_hr1.error("**Fase 1: Capitulation**\n\nSMA 30 scende sotto SMA 60. I minatori stanno fallendo e vendono BTC per sopravvivere. Prezzo sotto forte pressione.")
    c_hr2.warning("**Fase 2: Recovery**\n\nL'Hash Rate smette di scendere. Le macchine inefficienti sono state spente, il mercato inizia a stabilizzarsi.")
    c_hr3.success("**Fase 3: BUY SIGNAL**\n\nSMA 30 incrocia al rialzo la SMA 60. I minatori tornano in profitto. Storicamente ha segnalato **tutti** i minimi assoluti di Bitcoin.")
    
    st.markdown("---")
    
    st.header("₿ Il Mayer Multiple")
    st.write("Misura l'estensione del prezzo di Bitcoin rispetto alla sua media storica di lungo periodo, per evitare di comprare i massimi per FOMO (Fear Of Missing Out).")
    st.markdown("**Formula:** `Prezzo Attuale BTC` / `Media Mobile a 200 Giorni (200DMA)`")
    
    st.markdown("""
    * 🟩 **Sotto 1.0:** Accumulo perfetto. Il prezzo è sotto la sua media a 200 giorni (Tipico dei bear market estremi).
    * 🟨 **1.0 - 2.0:** Mercato rialzista sano (Uptrend).
    * 🟧 **2.0 - 2.4:** Surriscaldamento. Fase avanzata del ciclo.
    * 🟥 **Sopra 2.4:** Euforia irrazionale. È il momento matematico in cui i grandi fondi iniziano a vendere e prendere profitti.
    """)
