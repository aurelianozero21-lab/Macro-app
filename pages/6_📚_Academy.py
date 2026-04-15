import streamlit as st

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Academy", page_icon="📚", layout="wide")

st.title("📚 Academy: Investire con Semplicità")
st.write("Dimentica le formule matematiche complesse e i paroloni di Wall Street. In questa sezione ti spieghiamo come funzionano i mercati usando il buon senso e semplici analogie della vita reale.")

st.markdown("---")

# Divisione in 4 sottomoduli semplici
tab_macro, tab_azioni, tab_crypto, tab_app = st.tabs([
    "🌍 1. Le Basi dell'Economia", 
    "📈 2. Capire le Azioni", 
    "⚡ 3. Il Mondo Crypto",
    "🛠️ 4. Guida all'Applicazione"
])

# ==========================================
# MODULO 1: MACROECONOMIA BASE
# ==========================================
with tab_macro:
    st.header("🌍 Le forze che muovono il mondo")
    st.write("L'economia funziona esattamente come il motore di un'auto. Ci sono acceleratori e freni che determinano la velocità a cui andiamo.")
    
    st.subheader("1. I Tassi di Interesse (Il Costo del Denaro)")
    st.write("Immagina i tassi di interesse come il 'prezzo' per affittare i soldi. Chi decide questo prezzo? Le Banche Centrali (come la FED in America o la BCE in Europa).")
    col1, col2 = st.columns(2)
    with col1:
        st.success("**Tassi Bassi (Acceleratore) 🟢**\n\nPrendere in prestito soldi costa pochissimo. Le aziende chiedono prestiti per espandersi, le persone fanno mutui per comprare case. L'economia corre e i mercati azionari salgono.")
    with col2:
        st.error("**Tassi Alti (Freno) 🔴**\n\nPrendere soldi in prestito costa troppo. Le aziende smettono di assumere, la gente smette di comprare case. L'economia rallenta e i mercati scendono.")

    st.markdown("---")
    
    st.subheader("2. L'Inflazione (La tassa invisibile)")
    st.write("L'inflazione è l'aumento dei prezzi nel tempo. Se l'inflazione è al 5%, significa che il carrello della spesa che l'anno scorso pagavi 100€, oggi ti costa 105€.")
    st.info("💡 **Perché è importante?** Se tieni i tuoi soldi fermi sul conto corrente mentre c'è inflazione, stai tecnicamente perdendo potere d'acquisto ogni singolo giorno. Investire serve proprio a far crescere i tuoi soldi più velocemente di quanto salgono i prezzi.")

# ==========================================
# MODULO 2: AZIONI E MERCATI
# ==========================================
with tab_azioni:
    st.header("📈 Come funziona la Borsa")
    
    st.subheader("Cos'è un'Azione e cos'è l'S&P 500?")
    st.write("Comprare un'azione significa comprare un piccolissimo pezzetto di un'azienda vera (come Apple, Amazon o Ferrari). Se l'azienda vende di più e fa profitti, il tuo pezzetto vale di più.")
    st.write("L'**S&P 500** è semplicemente un 'cesto' (chiamato Indice o ETF) che contiene le 500 aziende più grandi e forti d'America. Comprando l'S&P 500, compri un pezzetto di tutta l'economia americana in un colpo solo, abbassando tantissimo il rischio.")

    st.markdown("---")

    st.subheader("La Regola d'Oro: Diversificazione e Rischio")
    st.write("Il rischio in finanza non significa solo 'perdere soldi', ma indica quanto il prezzo fa 'su e giù' in modo violento (Volatilità).")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.warning("**Tutte le uova in un paniere**\n\nSe compri solo azioni di una singola azienda tecnologica e quell'azienda va in crisi, perdi tutto. Questo è il rischio che vogliamo evitare.")
    with col_a2:
        st.success("**Il Portafoglio Bilanciato**\n\nMescolando Azioni (che crescono nel tempo), Obbligazioni/Bonds (che sono come prestiti sicuri) e Cash, crei un portafoglio che resiste a qualsiasi tempesta.")

# ==========================================
# MODULO 3: CRYPTO
# ==========================================
with tab_crypto:
    st.header("⚡ Il Mercato delle Criptovalute")
    
    st.subheader("Bitcoin vs Altcoin")
    st.write("Il mercato crypto si divide in due grandi categorie, e confonderle è l'errore più costoso che puoi fare:")
    
    st.markdown("""
    * 🟠 **Bitcoin (BTC):** Pensalo come l'"Oro Digitale". È nato per essere una riserva di valore sicura, limitata (non ce ne saranno mai più di 21 milioni) e che nessuno può censurare o bloccare.
    * 🔵 **Altcoin (Tutte le altre):** Pensale come delle "Startup Tecnologiche". Provano a creare nuove tecnologie (velocità, contratti intelligenti, giochi). Alcune faranno il +1000%, ma il 95% di esse fallirà scomparendo per sempre.
    """)

    st.markdown("---")
    
    st.subheader("I Cicli del Bitcoin (L'Halving)")
    st.write("A differenza dei soldi normali che possono essere stampati all'infinito, la produzione di nuovi Bitcoin è regolata da un timer matematico. Ogni 4 anni, la quantità di nuovi Bitcoin creati ogni giorno viene tagliata esattamente a metà. Questo evento si chiama **Halving**.")
    st.info("💡 **Cosa significa per i prezzi?** Storicamente, tagliando la nuova offerta a metà, se la domanda delle persone rimane uguale o sale, il prezzo è costretto a salire. Questo crea i famosi 'Cicli' di 4 anni del mercato crypto.")

# ==========================================
# MODULO 4: GUIDA ALL'APP
# ==========================================
with tab_app:
    st.header("🛠️ Come leggere i nostri indicatori")
    st.write("In questa applicazione usiamo dei sensori che sembrano complessi, ma che hanno significati molto pratici. Ecco un dizionario veloce:")
    
    with st.expander("📉 Cos'è la Curva dei Rendimenti (Yield Curve)?"):
        st.write("Normalmente, se presti soldi per 10 anni vieni pagato di più rispetto a prestarli per 2 anni (perché il tempo è un rischio). Quando succede il contrario (Inversione), significa che le banche hanno una paura tremenda del futuro immediato. È l'allarme antincendio più affidabile per le recessioni.")

    with st.expander("😰 Cos'è il VIX (Termometro del Panico)?"):
        st.write("Misura quanta 'assicurazione' stanno comprando i grandi fondi contro un crollo del mercato. Se il VIX è basso, c'è calma e ottimismo. Se il VIX schizza alle stelle, c'è panico totale (che spesso si rivela essere il momento migliore per comprare a sconto).")

    with st.expander("📉 Cos'è il Max Drawdown (nella scheda Risk Manager)?"):
        st.write("È un concetto fondamentale per la sopravvivenza. Indica **la perdita più grande che avresti subito** se avessi comprato nel momento peggiore assoluto. Se il tuo portafoglio ha un Max Drawdown del -40%, chiediti: *'Riuscirei a dormire la notte vedendo i miei 10.000€ scendere a 6.000€ senza vendere per il panico?'*")

    with st.expander("⛓️ Cos'è l'Hash Ribbon (nella scheda Crypto)?"):
        st.write("I 'Minatori' di Bitcoin sono aziende giganti con capannoni pieni di computer. Quando il prezzo di Bitcoin scende troppo, queste aziende vanno in perdita e spengono i computer (Capitolazione). L'Hash Ribbon ci avvisa quando hanno smesso di spegnere i computer: storicamente, quello è il fondo del barile e un ottimo momento per investire.")
