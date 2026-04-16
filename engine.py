import yfinance as yf
import pandas as pd
from fredapi import Fred
import feedparser
import urllib.request
import json
import requests
import streamlit as st
import datetime

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

def init_supabase():
    if SUPABASE_AVAILABLE and "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    return None

@st.cache_data(ttl=300)
def get_live_prices():
    """Recupera i prezzi live e li converte rigorosamente in numeri singoli."""
    tickers_list = ['BTC-USD', '^VIX', 'GC=F', '^GSPC', 'CL=F']
    prices = {}
    for t in tickers_list:
        try:
            d = yf.download(t, period="1d", interval="1m", progress=False, threads=False)
            if not d.empty:
                val = d['Close'].iloc[-1]
                # Se val è una Serie (tabellina), prendiamo il primo numero assoluto
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                prices[t] = float(val)
            else:
                prices[t] = 0.0
        except:
            prices[t] = 0.0
    return prices

def check_smart_alerts(df, live_prices, tension_index, hash_status=""):
    alerts = []
    if df.empty:
        return alerts
        
    current = df.iloc[-1]
    
    # Estrazione sicura del VIX (lo forziamo a diventare un numero puro)
    try:
        vix_live = live_prices.get('^VIX', current.get('VIX', 0))
        if isinstance(vix_live, pd.Series): vix_live = vix_live.iloc[0]
        if float(vix_live) > 28:
            alerts.append("🚨 PANICO SUI MERCATI: Il VIX ha superato quota 28. Possibile crash azionario in corso.")
    except: pass
        
    if tension_index >= 70:
        alerts.append("🔥 ALLARME GEOPOLITICA: Indice di tensione alle stelle (>70). Controlla il prezzo dell'Oro e del Petrolio.")
        
    try:
        z_sp = current.get('Z_S&P 500', 0)
        z_hy = current.get('Z_High Yield', 0)
        if isinstance(z_sp, pd.Series): z_sp = z_sp.iloc[0]
        if isinstance(z_hy, pd.Series): z_hy = z_hy.iloc[0]
        if float(z_sp) > 0 and float(z_hy) < -1:
            alerts.append("⚠️ DIVERGENZA FATALE: L'S&P 500 sta salendo ma il mercato del credito spazzatura sta crollando. Le banche stanno uscendo.")
    except: pass
        
    try:
        btc_live = live_prices.get('BTC-USD', current.get('Bitcoin', 0))
        if isinstance(btc_live, pd.Series): btc_live = btc_live.iloc[0]
        
        btc_ieri = df['Bitcoin'].iloc[-2]
        if isinstance(btc_ieri, pd.Series): btc_ieri = btc_ieri.iloc[0]
        
        variazione_btc = ((float(btc_live) - float(btc_ieri)) / float(btc_ieri)) * 100
        if variazione_btc < -7:
            alerts.append(f"🩸 CRYPTO CRASH: Bitcoin sta perdendo oltre il 7% oggi ({variazione_btc:.1f}%).")
        elif variazione_btc > 7:
            alerts.append(f"🚀 CRYPTO PUMP: Bitcoin in volo di oltre il 7% oggi ({variazione_btc:.1f}%).")
    except:
        pass
        
    try:
        yc_oggi = df['YieldCurve'].iloc[-1]
        yc_ieri = df['YieldCurve'].iloc[-2]
        if isinstance(yc_oggi, pd.Series): yc_oggi = yc_oggi.iloc[0]
        if isinstance(yc_ieri, pd.Series): yc_ieri = yc_ieri.iloc[0]
        if float(yc_ieri) > 0 and float(yc_oggi) < 0:
            alerts.append("☠️ INVERSIONE DELLA CURVA: I tassi a 2 anni hanno appena superato i decennali. Il timer della recessione è partito.")
    except:
        pass
        
    if "CAPITULATION" in hash_status:
        alerts.append("⛓️ ALLERTA ON-CHAIN: I Minatori di Bitcoin sono in Capitolazione (spengono le macchine). Spesso segna il minimo assoluto del mercato.")
    elif "BUY SIGNAL" in hash_status:
        alerts.append("💎 SEGNALE ON-CHAIN: I Minatori stanno ripartendo. Questo è storicamente uno dei più forti segnali di acquisto per Bitcoin.")
        
    return alerts

@st.cache_data(ttl=86400)
def get_shiller_pe():
    try:
        url = 'https://www.multpl.com/shiller-pe/table/by-month'
        # Indossiamo una "maschera" da browser per aggirare l'anti-bot
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=10)
        
        tables = pd.read_html(r.text)
        df_cape = tables[0]
        df_cape.columns = ['Date', 'CAPE']
        df_cape['Date'] = pd.to_datetime(df_cape['Date'])
        # Estraiamo solo il numero ignorando scritte come "estimate"
        df_cape['CAPE'] = df_cape['CAPE'].astype(str).str.extract(r'([0-9.]+)').astype(float)
        df_cape.set_index('Date', inplace=True)
        df_cape = df_cape.sort_index().resample('D').ffill()
        return df_cape['CAPE']
    except Exception as e:
        print(f"Errore CAPE: {e}")
        return pd.Series(dtype=float)

@st.cache_data(ttl=43200)
def get_onchain_metrics():
    try:
        url = "https://api.blockchain.info/charts/hash-rate?timespan=3years&format=json"
        res = requests.get(url).json()
        
        df_hash = pd.DataFrame(res['values'])
        df_hash['x'] = pd.to_datetime(df_hash['x'], unit='s')
        df_hash.set_index('x', inplace=True)
        df_hash.columns = ['HashRate']
        
        df_hash['SMA30'] = df_hash['HashRate'].rolling(window=30).mean()
        df_hash['SMA60'] = df_hash['HashRate'].rolling(window=60).mean()
        
        current = df_hash.iloc[-1]
        
        if current['SMA30'] < current['SMA60']:
            hash_status = "🔴 MINER CAPITULATION (Rischio/Bottoming)"
        else:
            if df_hash['SMA30'].iloc[-10] < df_hash['SMA60'].iloc[-10]:
                hash_status = "🟢 BUY SIGNAL (Fine Capitolazione)"
            else:
                hash_status = "📈 TREND SANO (Miners in Espansione)"
                
        return hash_status, df_hash
    except Exception as e:
        return "N/A", pd.DataFrame()

@st.cache_data(ttl=7200)
def load_all_data(api_key, lookback):
    tickers_map = {
        'S&P 500': '^GSPC', 'Dollaro DXY': 'DX-Y.NYB', 'Oro': 'GC=F', 
        'Treasury 10Y': '^TNX', 'High Yield': 'HYG', 'VIX': '^VIX', 
        'Bond ETF': 'IEF', 'Bitcoin': 'BTC-USD'
    }
    
    df = pd.DataFrame()
    
    # Scarichiamo i dati UNO PER VOLTA (molto più sicuro contro i blocchi IP)
    for nome, ticker in tickers_map.items():
        try:
            # Usiamo threads=False per non insospettire Yahoo
            data = yf.download(ticker, period="20y", progress=False, threads=False)
            if not data.empty:
                # Estraiamo la colonna Close (gestendo eventuali multi-index)
                if 'Close' in data.columns:
                    serie = data['Close']
                    if isinstance(serie, pd.DataFrame):
                        serie = serie.iloc[:, 0]
                    
                    serie.index = pd.to_datetime(serie.index).tz_localize(None).normalize()
                    df[nome] = serie
        except Exception as e:
            print(f"Salto {nome} causa errore: {e}")

    # Controllo critico: se non abbiamo scaricato NULLA
    if df.empty:
        st.error("⚠️ Yahoo Finance sta limitando l'accesso. Riprova tra pochi minuti.")
        return pd.DataFrame()

    # Riempire i buchi temporali (se un asset manca per qualche giorno)
    df = df.ffill()
    
    # Calcolo metriche Bitcoin SOLO SE la colonna esiste davvero
    if 'Bitcoin' in df.columns:
        df['BTC_ATH'] = df['Bitcoin'].cummax()
        df['BTC_Drawdown'] = ((df['Bitcoin'] - df['BTC_ATH']) / df['BTC_ATH']) * 100
        df['BTC_200DMA'] = df['Bitcoin'].rolling(window=200).mean()
        df['Mayer_BTC'] = df['Bitcoin'] / df['BTC_200DMA']
        
        delta_btc = df['Bitcoin'].diff()
        gain = delta_btc.where(delta_btc > 0, 0)
        loss = -delta_btc.where(delta_btc < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df['RSI_BTC'] = 100 - (100 / (1 + rs))
    else:
        # Se Bitcoin è fallito, creiamo colonne di "sicurezza" a zero
        for col in ['BTC_ATH', 'BTC_Drawdown', 'Mayer_BTC', 'RSI_BTC']:
            df[col] = 0.0

# Dati Macro (FRED)
    try:
        fred = Fred(api_key=api_key)
        df['YieldCurve'] = fred.get_series('T10Y2Y')
        
        # Scarichiamo i 3 pilastri della liquidità
        df['WALCL'] = fred.get_series('WALCL') # Bilancio FED (Milioni)
        df['WTREGEN'] = fred.get_series('WTREGEN') # TGA (Miliardi)
        df['RRPONTSYD'] = fred.get_series('RRPONTSYD') # Reverse Repo (Miliardi)
        
        # Sincronizziamo i giorni sfalsati di pubblicazione
        df['WALCL'] = df['WALCL'].ffill()
        df['WTREGEN'] = df['WTREGEN'].ffill()
        df['RRPONTSYD'] = df['RRPONTSYD'].ffill()
        
        # Formula Reale (Net Liquidity): Bilancio - TGA - RRP
        # Essendo in milioni e miliardi, sistemiamo gli zeri per avere i Trillioni
        df['Fed_Liquidity_T'] = (df['WALCL'] / 1000000) - (df['WTREGEN'] / 1000) - (df['RRPONTSYD'] / 1000)
    except Exception as e:
        print(f"Errore FRED: {e}")
        df['YieldCurve'] = 0.0
        df['Fed_Liquidity_T'] = 0.0
        
    
    # Calcolo Z-Score
    cols_to_z = ['S&P 500', 'Bitcoin', 'Oro', 'VIX']
    for col in cols_to_z:
        if col in df.columns:
            df[f'Z_{col}'] = (df[col] - df[col].rolling(window=lookback).mean()) / df[col].rolling(window=lookback).std()
            
    return df.dropna()
def calcola_backtest(df, pesi):
    try:
        # 1. Controllo di sicurezza: se il database è vuoto, fermati subito
        if df.empty:
            return pd.Series([10000.0]), pd.Series([10000.0]), 0.0, 0.0
            
        # Calcoliamo i rendimenti giornalieri
        rendimenti = df[['S&P 500', 'Bitcoin', 'Oro']].pct_change().dropna()
        
        # 2. Controllo di sicurezza: se dopo aver tolto i dati mancanti non resta nulla
        if rendimenti.empty:
             return pd.Series([10000.0]), pd.Series([10000.0]), 0.0, 0.0
        
        # Simuliamo un bond proxy
        rendimenti['Bonds'] = 0.04 / 252 
        
        # Calcoliamo il rendimento pesato del portafoglio
        rendimenti_portafoglio = (
            rendimenti['S&P 500'] * pesi.get('Azioni', 0) +
            rendimenti['Bonds'] * pesi.get('Bonds', 0) +
            rendimenti['Bitcoin'] * pesi.get('Crypto', 0) +
            rendimenti['Oro'] * pesi.get('Cash', 0) 
        )
        
        # Calcoliamo l'equity line (capitale cumulato partendo da 10.000$)
        capitale_iniziale = 10000
        equity_portafoglio = capitale_iniziale * (1 + rendimenti_portafoglio).cumprod()
        equity_benchmark = capitale_iniziale * (1 + rendimenti['S&P 500']).cumprod()
        
        # 3. Controllo di sicurezza finale prima della matematica
        if equity_portafoglio.empty:
            return pd.Series([10000.0]), pd.Series([10000.0]), 0.0, 0.0
            
        # Metriche di performance (usiamo max per evitare divisioni per zero se c'è un solo giorno)
        anni = max(len(rendimenti_portafoglio) / 252, 0.01)
        cagr = (equity_portafoglio.iloc[-1] / capitale_iniziale) ** (1 / anni) - 1
        
        # Max Drawdown
        picco_cumulativo = equity_portafoglio.cummax()
        drawdown = (equity_portafoglio - picco_cumulativo) / picco_cumulativo
        max_dd = drawdown.min() if not drawdown.empty else 0.0
        
        return equity_portafoglio, equity_benchmark, cagr, max_dd
        
    except Exception as e:
        print(f"Errore nel backtest: {e}")
        # Paracadute finale
        return pd.Series([10000.0]), pd.Series([10000.0]), 0.0, 0.0

# --- NUOVA FUNZIONE: STAGIONALITA' ---
def calcola_stagionalita(df, asset_name):
    if asset_name not in df.columns:
        return pd.DataFrame(), pd.DataFrame()
        
    # Copia i dati e calcola il rendimento percentuale giornaliero
    df_season = df[[asset_name]].copy()
    df_season['Rendimento'] = df_season[asset_name].pct_change()
    
    # Aggiunge colonne per Giorno dell'anno e Anno
    df_season['DayOfYear'] = df_season.index.dayofyear
    df_season['Year'] = df_season.index.year
    
    anno_corrente = datetime.datetime.now().year
    
    # Isola l'anno in corso (normalizzato a 100 il 1 Gennaio)
    df_corrente = df_season[df_season['Year'] == anno_corrente].copy()
    if not df_corrente.empty:
        df_corrente['Cumulative'] = (1 + df_corrente['Rendimento'].fillna(0)).cumprod() * 100
        
    # Calcola la media storica escludendo l'anno corrente
    df_storico = df_season[df_season['Year'] < anno_corrente]
    # Raggruppa per giorno dell'anno e fa la media dei rendimenti
    media_giornaliera = df_storico.groupby('DayOfYear')['Rendimento'].mean()
    
    # Ricostruisce un anno "medio" basato sulla stagionalità (base 100)
    df_media = pd.DataFrame({'DayOfYear': media_giornaliera.index, 'RendimentoMedio': media_giornaliera.values})
    df_media['Cumulative Storico'] = (1 + df_media['RendimentoMedio']).cumprod() * 100
    
    return df_corrente, df_media


@st.cache_data(ttl=7200)
def get_etf_screener():
    tickers = {'USA (SPY)': 'SPY', 'Europa (VGK)': 'VGK', 'Emergenti (EEM)': 'EEM', 'Giappone (EWJ)': 'EWJ', 'Tech (XLK)': 'XLK', 'Salute (XLV)': 'XLV', 'Finanza (XLF)': 'XLF', 'Energia (XLE)': 'XLE', 'Utilities (XLU)': 'XLU', 'Industria (XLI)': 'XLI'}
    dati = []
    try:
        lista_tk = list(tickers.values())
        data = yf.download(lista_tk, period="1y", progress=False)
        if 'Close' in data:
            for nome, tk in tickers.items():
                hist = data['Close'][tk].dropna()
                if len(hist) > 50:
                    prezzo, sma_50, sma_200 = hist.iloc[-1], hist.tail(50).mean(), hist.mean() 
                    perf_1m = ((prezzo / hist.iloc[-21]) - 1) * 100
                    segnale = "🟢 Compra" if prezzo > sma_50 and sma_50 > sma_200 else "🟡 Accumula" if prezzo > sma_50 else "🔴 Evita"
                    tipo = 'Geografia' if tk in ['SPY', 'VGK', 'EEM', 'EWJ'] else 'Settore'
                    dati.append({'Categoria': tipo, 'Asset': nome, 'Prezzo ($)': round(prezzo, 2), 'Perf. 1 Mese (%)': round(perf_1m, 2), 'Segnale Operativo': segnale})
    except: pass
    return pd.DataFrame(dati)

@st.cache_data(ttl=7200)
def get_crypto_screener():
    tickers = {'Bitcoin': 'BTC-USD', 'Ethereum': 'ETH-USD', 'Solana': 'SOL-USD', 'Binance': 'BNB-USD', 'Avalanche': 'AVAX-USD'}
    dati = []
    try:
        data = yf.download(list(tickers.values()), period="1y", progress=False)
        if 'Close' in data:
            for nome, tk in tickers.items():
                hist = data['Close'][tk].dropna()
                if len(hist) > 50:
                    prezzo, sma_50, sma_200 = hist.iloc[-1], hist.tail(50).mean(), hist.mean() 
                    perf_1m = ((prezzo / hist.iloc[-21]) - 1) * 100
                    dati.append({'Asset': nome, 'Prezzo ($)': round(prezzo, 2), 'Perf. 1 Mese (%)': round(perf_1m, 2)})
    except: pass
    return pd.DataFrame(dati)

@st.cache_data(ttl=3600)
def get_crypto_fgi():
    try:
        with urllib.request.urlopen("https://api.alternative.me/fng/") as url:
            data = json.loads(url.read().decode())
            return int(data['data'][0]['value']), data['data'][0]['value_classification']
    except: return 50, "Neutral"

@st.cache_data(ttl=3600)
def analyze_geopolitics():
    url = "https://news.google.com/rss/search?q=geopolitics+OR+sanctions+OR+conflict+OR+economy+markets&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        if not feed.entries: return 50, [], {}
        risk_words, peace_words = ['war', 'strike', 'tariff', 'sanction', 'missile', 'tension', 'conflict'], ['peace', 'deal', 'agreement', 'ceasefire', 'talks']
        regions = {'Medio Oriente': ['israel', 'iran', 'gaza', 'yemen'], 'Est Europa': ['russia', 'ukraine', 'putin', 'nato'], 'Asia-Pacifico': ['china', 'taiwan', 'beijing', 'xi']}
        region_scores, score_totale, news_items = {'Medio Oriente': 0, 'Est Europa': 0, 'Asia-Pacifico': 0}, 0, []
        for entry in feed.entries[:25]:
            titolo = entry.title.lower()
            item_score = sum(1 for w in risk_words if w in titolo) - sum(1 for w in peace_words if w in titolo)
            score_totale += item_score
            for region, keywords in regions.items():
                if any(kw in titolo for kw in keywords): region_scores[region] += 1
            if item_score != 0 and len(news_items) < 8: news_items.append({'titolo': entry.title, 'link': entry.link, 'score': item_score})
        return max(0, min(100, 50 + (score_totale * 4))), news_items, region_scores
    except:
        return 50, [], {}

def calcola_fase_avanzata(yc, z_sp500, tension):
    if yc < 0 or tension >= 65: return '1. Allarme Rosso (Risk-Off)'
    elif yc > 0 and (z_sp500 < 0 or tension >= 50): return '2. Incertezza / Accumulo Difensivo'
    else: return '3. Espansione (Risk-On)'

def get_telegram_link():
    return st.secrets.get("TG_BOT_URL", "https://t.me/tuobot")

def calcola_orologio_ciclo(df):
    """
    Calcola la fase attuale dell'Orologio del Ciclo Economico di Merrill Lynch.
    Usa lo Z-Score dell'S&P 500 come proxy di crescita e l'Oro come proxy di inflazione.
    """
    try:
        current = df.iloc[-1]
        crescita = current.get('Z_S&P 500', 0)
        inflazione = current.get('Z_Oro', 0)
        
        fase = ""
        descrizione = ""
        asset_consigliato = ""
        colore = ""

        # Quadrante 2: Ripresa (Crescita +, Inflazione -)
        if crescita > 0 and inflazione < 0:
            fase = "Ripresa (Fase 2)"
            descrizione = "La crescita accelera, ma i prezzi sono sotto controllo."
            asset_consigliato = "📈 Azioni (Tech, Industriali)"
            colore = "success"
            
        # Quadrante 3: Surriscaldamento (Crescita +, Inflazione +)
        elif crescita > 0 and inflazione >= 0:
            fase = "Surriscaldamento (Fase 3)"
            descrizione = "L'economia è rovente. L'inflazione inizia a salire."
            asset_consigliato = "🛢️ Materie Prime (Energia, Oro)"
            colore = "warning"
            
        # Quadrante 4: Stagflazione (Crescita -, Inflazione +)
        elif crescita <= 0 and inflazione >= 0:
            fase = "Stagflazione (Fase 4)"
            descrizione = "La crescita frena bruscamente, ma i prezzi restano alti."
            asset_consigliato = "💵 Liquidità (Cash) e Difensivi"
            colore = "error"
            
        # Quadrante 1: Reflazione (Crescita -, Inflazione -)
        else:
            fase = "Reflazione (Fase 1)"
            descrizione = "L'economia è debole, le banche tagliano i tassi."
            asset_consigliato = "🏦 Obbligazioni (Bonds Governativi)"
            colore = "normal"

        return fase, descrizione, asset_consigliato, colore
    except Exception as e:
        return "Sconosciuta", "Dati insufficienti", "N/A", "normal"

def get_real_btc_dominance():
    """
    Recupera la Bitcoin Dominance reale in tempo reale dall'API pubblica di CoinGecko.
    """
    try:
        url = "https://api.coingecko.com/api/v3/global"
        response = requests.get(url, timeout=5)
        data = response.json()
        # Estrae la dominance esatta di BTC dal totale del mercato
        btc_dom = data['data']['market_cap_percentage']['btc']
        return btc_dom
    except Exception as e:
        # Fallback di sicurezza in caso i server di CoinGecko siano intasati
        return 54.0
