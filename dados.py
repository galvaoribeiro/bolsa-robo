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
        for ano in range(int(INICIO[:4]), date.today().year + 1, 5):
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
