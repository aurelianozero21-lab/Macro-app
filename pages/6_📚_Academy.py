import streamlit as st
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Quant Academy", page_icon="📚", layout="wide")

st.title("📚 Quant Academy: Masterclass Istituzionale")
st.write("I principi matematici, economici e statistici che alimentano l'intelligenza di questa piattaforma. Capire il *perché* le cose accadono è l'unico vantaggio competitivo sui mercati.")

st.markdown("---")

# Divisione in 4 sottomoduli
mod_macro, mod_risk, mod_crypto, mod_math = st.tabs([
    "🏛️ 1: Motori Macroeconomici", 
    "⚖️ 2: Valutazione & Sentiment", 
    "⛓️ 3: Dinamiche On-Chain",
    "🧮 4: Matematica di Portafoglio"
])

# ==========================================
# MODULO 1: MACROECONOMIA
# ==========================================
with mod_macro:
    st.header("🌊 La Liquidità Netta (Net Liquidity)")
    st.write("Nel mercato moderno, la quantità di denaro nel sistema guida i prezzi degli asset a rischio (Azioni, Crypto) più degli utili aziendali.")
    
    st.latex(r"Net\ Liquidity = Total\ Assets\ (FED) - TGA - RRP")
    
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.info("**Componenti:**\n* **Total Assets:** Il bilancio della FED (denaro stampato).\n* **TGA (Treasury General Account):** Il conto corrente del governo. Se il governo lo riempie, toglie soldi al mercato.\n* **RRP (Reverse Repo):** Parcheggio di liquidità per le banche.")
    with col_l2:
        st.error("**Regola Operativa:**\nQuando la Liquidità scende (QT), i mercati faticano e i multipli si comprimono. È il momento di difendersi. Quando la Liquidità sale, è il momento di prendere rischio (Buy the dip).")

    st.markdown("---")
    
    st.header("☠️ L'Inversione della Curva dei Rendimenti")
    st.write("La differenza di rendimento tra i Titoli di Stato a 10 anni (Lungo Termine) e a 2 anni (Breve Termine). Ha previsto con il 100% di precisione ogni recessione dal 1970.")
    
    st.latex(r"Spread = Yield_{10Y} - Yield_{2Y}")
    
    c_y1, c_y2, c_y3 = st.columns(3)
    c_y1.success("**Curva Normale (Spread > 0)**\n\nL'economia cresce. Il rischio a lungo termine è pagato di più. Fase costruttiva per le azioni.")
    c_y2.error("**Curva Invertita (Spread < 0)**\n\nIl mercato teme il breve termine. Iniziano i campanelli d'allarme, ma le azioni spesso fanno un ultimo rally (Late Cycle).")
    c_y3.warning("**Re-Steepening (Ritorno a > 0)**\n\nLa curva torna positiva velocemente perché le banche centrali tagliano i tassi in preda al panico. **Storicamente, è qui che iniziano i veri crolli azionari.**")

# ==========================================
# MODULO 2: VALUTAZIONE E SENTIMENT
# ==========================================
with mod_risk:
    st.header("🏛️ Shiller P/E (CAPE Ratio) e i suoi limiti")
    st.write("Valuta l'S&P 500 dividendo il prezzo per la media degli utili degli ultimi 10 anni aggiustati per l'inflazione, smussando così le fluttuazioni economiche di breve periodo.")
    
    st.markdown("""
    | Valore CAPE | Significato Storico | Posizionamento Statistico |
    | :--- | :--- | :--- |
    | **Sotto 15** | Sottovalutazione Estrema | Accumulo aggressivo (Equity Risk Premium altissimo) |
    | **15 - 25** | Fair Value / Media Storica | Portafoglio bilanciato standard |
    | **25 - 30** | Sopravvalutazione | Rotazione verso settori difensivi / value |
    | **Sopra 30** | **Bolla Speculativa** | Riduzione drastica del rischio (1929, 2000, 2021) |
    """)
    
    with st.expander("🔍 Il limite del CAPE (L'effetto Tassi di Interesse)"):
        st.write("Il CAPE non tiene conto dei tassi di interesse. Un CAPE a 30 è pericolosissimo se i tassi sono al 5%, ma è 'giustificabile' se i tassi sono allo 0% (perché non ci sono alternative di rendimento). I veri quantitativi usano l'**ECY (Excess CAPE Yield)** per confrontarlo con i rendimenti dei bond.")

    st.markdown("---")
    
    st.header("📊 VIX & Term Structure (Il VERO indicatore di Paura)")
    st.write("Tutti conoscono il VIX (Indice di Volatilità), ma pochi sanno leggerne la struttura. Non conta solo il numero, conta la forma della curva della volatilità futura.")
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        st.success("**Contango (Normalità)**\n\nIl VIX a 1 mese è più BASSO del VIX a 3 mesi. Il mercato è tranquillo, si aspetta che i rischi siano lontani nel tempo. Trend rialzista intatto.")
    with col_v2:
        st.error("**Backwardation (Panico)**\n\nIl VIX a 1 mese schizza SOPRA il VIX a 3 mesi. Gli operatori pagano cifre folli per assicurarsi contro un crollo *immediato*. Segna spesso i minimi di mercato (Bottom).")

# ==========================================
# MODULO 3: ON-CHAIN & CRYPTO
# ==========================================
with mod_crypto:
    st.header("⛓️ Hash Ribbon e la Capitolazione")
    st.write("Legge la redditività industriale della rete Bitcoin. Quando i prezzi crollano o l'algoritmo diventa troppo difficile (Difficulty Adjustment), i minatori vanno in perdita, spengono l'hardware e scaricano BTC sul mercato.")
    
    c_hr1, c_hr2, c_hr3 = st.columns(3)
    c_hr1.error("**1. Capitulation**\n\nSMA(30) < SMA(60). Minatori in crisi di liquidità. Pressione di vendita massima.")
    c_hr2.warning("**2. Recovery**\n\nL'Hash Rate smette di crollare. Le macchine obsolete sono fuori, il mercato assorbe le vendite.")
    c_hr3.success("**3. Buy Signal**\n\nSMA(30) > SMA(60). Ritorno alla redditività. Uno dei segnali di acquisto più affidabili a lungo termine.")
    
    st.markdown("---")

    st.header("⚖️ MVRV Z-Score (Market Value vs Realized Value)")
    st.write("L'indicatore definitivo per identificare Top e Bottom del Bitcoin. Confronta la capitalizzazione attuale (Market Cap) con il valore a cui sono state mosse per l'ultima volta tutte le monete (Realized Cap).")
    
    st.latex(r"MVRV\ Z-Score = \frac{Market\ Cap - Realized\ Cap}{StdDev(Market\ Cap)}")
    
    st.info("**Lettura:**\n* **Zona Verde (Z-Score < 0.1):** Accumulo generazione. Il mercato valuta BTC meno di quanto è costato storicamente agli investitori.\n* **Zona Rossa (Z-Score > 7.0):** Bolla pura. Tutti sono in profitti mostruosi, incentivo matematico a vendere altissimo.")

# ==========================================
# MODULO 4: MATEMATICA DI PORTAFOGLIO
# ==========================================
with mod_math:
    st.header("🧮 L'Aritmetica della Rovina (Drawdown Math)")
    st.write("Il cervello umano pensa in modo lineare, ma le perdite finanziarie funzionano in modo asimmetrico. Maggiore è la perdita (Drawdown), esponenzialmente maggiore dovrà essere il guadagno solo per tornare in pari.")
    
    # Tabella matematica del drawdown
    dd_data = {
        "Perdita Subita (Drawdown)": ["-10%", "-20%", "-33%", "-50%", "-75%", "-90%"],
        "Performance necessaria per recuperare": ["+11%", "+25%", "+50%", "+100%", "+300%", "+900%"]
    }
    st.table(pd.DataFrame(dd_data))
    st.write("Ecco perché il **Risk Management (Gestione del Rischio)** e la diversificazione (Bond/Oro) contano più della capacità di scegliere le azioni giuste.")
    
    st.markdown("---")
    
    st.header("⚖️ Sharpe Ratio (Rendimento Aggiustato per il Rischio)")
    st.write("Tutti sanno calcolare il guadagno, ma quanto rischio hai corso per ottenerlo? Lo Sharpe Ratio divide il tuo rendimento in eccesso (rispetto a un investimento senza rischio, come i Bot BOT) per la volatilità del tuo portafoglio.")
    
    st.latex(r"Sharpe\ Ratio = \frac{R_p - R_f}{\sigma_p}")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.write("**Legenda:**\n* $R_p$ = Rendimento del tuo portafoglio\n* $R_f$ = Tasso privo di rischio (Risk-Free Rate)\n* $\sigma_p$ = Deviazione standard (Volatilità)")
    with col_s2:
        st.write("**Come leggerlo:**\n* **< 1.0:** Sub-ottimale. Stai rischiando troppo per i rendimenti che ottieni.\n* **1.0 - 2.0:** Ottimo portafoglio.\n* **> 2.0:** Performance da fuoriclasse istituzionale.")
