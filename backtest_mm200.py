"""
Backtest da Etapa 1: BOVA11 acima/abaixo da média móvel de 200 dias.

Regra (avaliada só com o fechamento do dia, então roda à noite, fora do expediente):
  - Fechamento > MM200  -> ficar comprado no dia seguinte
  - Fechamento <= MM200 -> ficar fora (em caixa/CDI) no dia seguinte

Uso:
  pip install yfinance pandas
  python backtest_mm200.py                 # baixa BOVA11.SA do Yahoo
  python backtest_mm200.py --csv dados.csv # usa um CSV com colunas Date, Close

O que o script faz para não se enganar:
  - Sinal de hoje só vale a partir de amanhã (shift(1)): sem olhar o futuro.
  - Custo por troca de posição (corretagem + emolumentos + slippage).
  - Compara com "comprar e segurar" no mesmo período.
  - Separa o período em dois: dentro da amostra e fora da amostra.
"""
import argparse

import numpy as np
import pandas as pd

CUSTO_POR_TROCA = 0.001   # 0,10% por entrada ou saída (estimativa conservadora)
CDI_ANUAL = 0.10          # rendimento do caixa quando fora (simplificação)


def carregar(ticker: str, csv: str | None) -> pd.Series:
    if csv:
        df = pd.read_csv(csv, parse_dates=["Date"], index_col="Date")
        return df["Close"].dropna()
    import yfinance as yf
    df = yf.download(ticker, start="2010-01-01", progress=False, auto_adjust=True)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):  # yfinance novo devolve colunas multi-índice
        close = close.iloc[:, 0]
    return close.dropna()


def backtest(close: pd.Series, janela: int = 200) -> pd.DataFrame:
    mm = close.rolling(janela).mean()
    sinal = (close > mm).astype(int)
    posicao = sinal.shift(1).fillna(0)            # decide hoje, executa amanhã
    ret_ativo = close.pct_change().fillna(0)
    ret_caixa = (1 + CDI_ANUAL) ** (1 / 252) - 1
    trocas = posicao.diff().abs().fillna(0)
    ret = posicao * ret_ativo + (1 - posicao) * ret_caixa - trocas * CUSTO_POR_TROCA
    out = pd.DataFrame({"close": close, "mm": mm, "posicao": posicao,
                        "ret_estrategia": ret, "ret_buy_hold": ret_ativo, "trocas": trocas})
    return out.iloc[janela:]                      # descarta o período sem MM


def metricas(ret: pd.Series) -> dict:
    curva = (1 + ret).cumprod()
    anos = len(ret) / 252
    cagr = curva.iloc[-1] ** (1 / anos) - 1 if anos > 0 else np.nan
    vol = ret.std() * np.sqrt(252)
    drawdown = (curva / curva.cummax() - 1).min()
    return {"retorno_total": curva.iloc[-1] - 1, "cagr": cagr, "vol_anual": vol,
            "pior_queda": drawdown, "sharpe_aprox": (cagr - CDI_ANUAL) / vol if vol else np.nan}


def relatorio(nome: str, df: pd.DataFrame) -> None:
    print(f"\n=== {nome}: {df.index[0].date()} a {df.index[-1].date()} ===")
    for rotulo, col in [("Estratégia MM200", "ret_estrategia"), ("Comprar e segurar", "ret_buy_hold")]:
        m = metricas(df[col])
        print(f"{rotulo:18s} | total {m['retorno_total']:+8.1%} | ao ano {m['cagr']:+6.1%} | "
              f"vol {m['vol_anual']:5.1%} | pior queda {m['pior_queda']:+6.1%} | "
              f"sharpe~ {m['sharpe_aprox']:+.2f}")
    print(f"Trocas de posição: {int(df['trocas'].sum())} | tempo comprado: {df['posicao'].mean():.0%}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", default="BOVA11.SA")
    p.add_argument("--csv")
    p.add_argument("--janela", type=int, default=200)
    a = p.parse_args()

    df = backtest(carregar(a.ticker, a.csv), a.janela)
    meio = len(df) // 2
    relatorio("Período completo", df)
    relatorio("1ª metade (dentro da amostra)", df.iloc[:meio])
    relatorio("2ª metade (fora da amostra)", df.iloc[meio:])

    ultimo = df.iloc[-1]
    acao = "COMPRADO" if ultimo["close"] > ultimo["mm"] else "FORA"
    print(f"\nSinal para o próximo pregão: {acao} "
          f"(fechamento {ultimo['close']:.2f} vs MM{a.janela} {ultimo['mm']:.2f})")


if __name__ == "__main__":
    main()
