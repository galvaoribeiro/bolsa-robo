"""
Triagem de limite superior: todas as carteiras compradas do NEFIN (sem viés de sobrevivência, SEM custos),
puras e com filtro de tendência do Ibovespa (6 e 10 meses). Se nenhuma passar nos critérios 1–4 nem assim,
nenhuma versão implementável (com custos) desses estilos passará.

Uso: python triagem_nefin.py
"""
from pathlib import Path

import pandas as pd

import dados
import motor

ARQS = ["3_portfolios_sorted_by_book_to_market", "3_portfolios_sorted_by_illiquidity",
        "3_portfolios_sorted_by_momentum", "3_portfolios_sorted_by_size",
        "4_portfolios_sorted_by_size_and_book_to_market_2x2", "4_portfolios_sorted_by_size_and_illiquidity_2x2",
        "4_portfolios_sorted_by_size_and_momentum_2x2", "7_portfolios_sorted_by_industry"]


def main():
    cdi = dados.cdi()
    ib = dados.multiativos()["IBOV"]
    ibm = ib.groupby([ib.index.year, ib.index.month]).tail(1)
    n, passam, linhas = 0, [], []
    for arq in ARQS:
        for aba in ["Equally Weighted Returns", "Value Weighted Returns"]:
            x = pd.read_excel(Path("dados/nefin") / f"{arq}.xls", sheet_name=aba)
            x.index = pd.to_datetime(dict(year=x.year, month=x.month, day=x.day))
            x = x.drop(columns=["year", "month", "day"])["2004":]
            for col in x.columns:
                r = x[col]
                rf = cdi.reindex(r.index).fillna(0)
                for filtro in [None, 6, 10]:
                    if filtro:
                        pos = (ibm > ibm.rolling(filtro).mean()).astype(float)
                        pos = pos.reindex(r.index, method="ffill").shift(2).fillna(1)
                        ret = pos * r + (1 - pos) * rf
                    else:
                        ret = r
                    c = (1 + ret["2005":]).cumprod()
                    m = motor.metricas(c, cdi)
                    nome = f"{arq.split('_sorted_by_')[1][:22]} {aba[:2]} {col} {'filtro ' + str(filtro) + 'm' if filtro else 'puro'}"
                    n += 1
                    ok = all(motor.criterios_basicos(m).values())
                    linhas.append((m["sharpe"], motor.linha_texto(nome, m)))
                    if ok:
                        passam.append(nome)
    linhas.sort(reverse=True)
    print(f"{n} combinações (carteira × peso × filtro), sem custos. As 15 de maior Sharpe:")
    for _, l in linhas[:15]:
        print(l)
    print("\nPassam nos critérios 1–4 (sem custos):", passam if passam else "nenhuma")


if __name__ == "__main__":
    main()
