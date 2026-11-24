"""
Carregamento de dados com cache local em dados/ (para não baixar tudo de novo a cada teste).

- precos(tickers): OHLC diário ajustado (proventos e desdobramentos) do Yahoo Finance.
- cdi(): taxa diária do CDI (série 12 do Banco Central), em fração por dia útil.
"""
from datetime import date
from pathlib import Path

import pandas as pd

PASTA = Path(__file__).parent / "dados"
INICIO = "2010-01-01"


def precos(tickers: list[str], atualizar: bool = False) -> dict[str, pd.DataFrame]:
    """Devolve {ticker: DataFrame com Open, High, Low, Close}."""
    PASTA.mkdir(exist_ok=True)
    saida = {}
    faltando = [t for t in tickers if atualizar or not (PASTA / f"{t}.csv").exists()]
    if faltando:
        import yfinance as yf
        for t in faltando:
            df = yf.download(t, start=INICIO, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df[["Open", "High", "Low", "Close"]].dropna()
            df = df[(df > 0).all(axis=1)]
            df.to_csv(PASTA / f"{t}.csv")
    for t in tickers:
        saida[t] = pd.read_csv(PASTA / f"{t}.csv", index_col=0, parse_dates=True)
    return saida


def cdi(atualizar: bool = False) -> pd.Series:
    """CDI diário (ex.: 0.0004 = 0,04% no dia). O BC limita 10 anos por consulta."""
    arq = PASTA / "cdi.csv"
    if atualizar or not arq.exists():
        import json
        import urllib.request
        PASTA.mkdir(exist_ok=True)
        partes = []
        for ano in range(2000, date.today().year + 1, 5):
            fim = min(ano + 4, date.today().year)
            url = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json"
                   f"&dataInicial=01/01/{ano}&dataFinal=31/12/{fim}")
            with urllib.request.urlopen(url, timeout=60) as r:
                partes += json.load(r)
        s = pd.Series({pd.to_datetime(p["data"], dayfirst=True): float(p["valor"]) / 100
                       for p in partes}, name="cdi").sort_index()
        s.to_csv(arq, header=True)
    return pd.read_csv(arq, index_col=0, parse_dates=True)["cdi"]


def intraday(ticker: str, intervalo: str = "1m") -> pd.DataFrame:
    """Barras intradiárias (horário de Brasília). O Yahoo guarda pouco histórico (1m: ~30 dias,
    5m: ~60 dias), então cada download é JUNTADO ao cache: rodando com frequência, o histórico cresce."""
    import yfinance as yf
    from datetime import datetime, timedelta
    PASTA.mkdir(exist_ok=True)
    arq = PASTA / f"{ticker}_{intervalo}.csv"
    partes = []
    if intervalo == "1m":                       # Yahoo só entrega 1m em janelas de até 8 dias
        hoje = datetime.now()
        for k in range(4):
            fim, ini = hoje - timedelta(days=7 * k), hoje - timedelta(days=7 * (k + 1))
            partes.append(yf.download(ticker, start=ini.strftime("%Y-%m-%d"),
                                      end=(fim + timedelta(days=1)).strftime("%Y-%m-%d"),
                                      interval="1m", progress=False, auto_adjust=False))
    else:
        partes.append(yf.download(ticker, period="60d", interval=intervalo, progress=False, auto_adjust=False))
    novo = pd.concat([p for p in partes if len(p)])
    if isinstance(novo.columns, pd.MultiIndex):
        novo.columns = novo.columns.get_level_values(0)
    novo = novo[["Open", "High", "Low", "Close", "Volume"]]
    novo.index = novo.index.tz_convert("America/Sao_Paulo").tz_localize(None)
    if arq.exists():
        novo = pd.concat([pd.read_csv(arq, index_col=0, parse_dates=True), novo])
    novo = novo[~novo.index.duplicated(keep="last")].sort_index()
    novo = novo[(novo[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    novo.to_csv(arq)
    return novo


def serie_bcb(codigo: int, nome: str, atualizar: bool = False) -> pd.Series:
    """Série diária do Banco Central (SGS). Ex.: 1 = dólar PTAX venda."""
    import json
    import urllib.request
    arq = PASTA / f"bcb_{codigo}.csv"
    if atualizar or not arq.exists():
        PASTA.mkdir(exist_ok=True)
        partes = []
        for ano in range(2000, date.today().year + 1, 5):
            fim = min(ano + 4, date.today().year)
            url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
                   f"&dataInicial=01/01/{ano}&dataFinal=31/12/{fim}")
            with urllib.request.urlopen(url, timeout=60) as r:
                partes += json.load(r)
        s = pd.Series({pd.to_datetime(p["data"], dayfirst=True): float(p["valor"]) for p in partes},
                      name=nome).sort_index()
        s.to_csv(arq, header=True)
    return pd.read_csv(arq, index_col=0, parse_dates=True)[nome]


def multiativos(taxas: bool = True) -> pd.DataFrame:
    """Índices de retorno total em REAIS, diários (dias úteis da B3), com taxa de administração descontada:
    IBOV (≈BOVA11), SPX (SPY × dólar ≈ IVVB11), OURO (GLD, antes de 2005 ouro futuro, × dólar ≈ GOLD11),
    DOLAR (PTAX), TREA (Treasuries 7-10 anos, IEF × dólar)."""
    global INICIO
    INICIO_ANT, INICIO = INICIO, "2000-01-01"
    p = precos(["^BVSP", "SPY", "GLD", "GC=F", "IEF"])
    INICIO = INICIO_ANT
    usd = serie_bcb(1, "usd")
    ibov = p["^BVSP"].Close
    datas = ibov.index
    gld, gcf = p["GLD"].Close, p["GC=F"].Close
    ouro_usd = pd.concat([gcf[:gld.index[0]] * gld.iloc[0] / gcf.reindex(gld.index).dropna().iloc[0],
                          gld[gld.index[0]:].iloc[1:]])
    usd_d = usd.reindex(datas).ffill()
    df = pd.DataFrame({
        "IBOV": ibov,
        "SPX": p["SPY"].Close.reindex(datas).ffill() * usd_d,
        "OURO": ouro_usd.reindex(datas).ffill() * usd_d,
        "DOLAR": usd_d,
        "TREA": p["IEF"].Close.reindex(datas).ffill() * usd_d,
    }).dropna()
    if taxas:                                      # taxa de administração anual aproximada dos ETFs na B3
        anos = (df.index - df.index[0]).days / 365.25
        for c, tx in {"IBOV": 0.001, "SPX": 0.008, "OURO": 0.003, "TREA": 0.008}.items():
            df[c] = df[c] * (1 - tx) ** anos
    return df
