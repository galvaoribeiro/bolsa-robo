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
