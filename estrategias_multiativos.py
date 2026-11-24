"""
Famílias 5 e 6 do PROTOCOLO.md: estratégias multiativos em reais (executáveis com ETFs da B3:
BOVA11, IVVB11, GOLD11, uma ETF de Treasuries ou fundo cambial, e Tesouro Selic para o caixa).

Família 5 — dual momentum (Antonacci): todo mês, o ativo de maior retorno em N meses;
            se esse retorno não superar o CDI do mesmo período, fica 100% no CDI.
Família 6 — tendência por ativo (Faber): cada ativo tem uma fatia; a fatia fica no ativo se o
            preço estiver acima da média de N meses, senão vai para o CDI. Pesos iguais ou pelo risco.
Referências: carteiras fixas (sem sinal) para comparação.

Uso: python estrategias_multiativos.py
"""
import numpy as np
import pandas as pd

import dados
import motor

CUSTO = 0.001


def preparar():
    m = dados.multiativos()
    cdi = dados.cdi()
    cdi_idx = (1 + cdi.reindex(m.index).fillna(0)).cumprod()
    mensal = m.groupby([m.index.year, m.index.month]).tail(1)
    return m, cdi, cdi_idx, mensal


def dual_momentum(m, cdi_idx, mensal, ativos, meses, n_top=1):
    def decidir(d):
        h = mensal[mensal.index <= d][ativos]
        if len(h) <= meses:
            return pd.Series(dtype=float)
        ret = h.iloc[-1] / h.iloc[-1 - meses] - 1
        ini = h.index[-1 - meses]
        ret_cdi = cdi_idx[d] / cdi_idx[ini] - 1
        top = ret.sort_values(ascending=False).head(n_top)
        top = top[top > ret_cdi]
        return pd.Series(1.0 / n_top, index=top.index)
    return decidir


def tendencia(m, cdi_idx, mensal, ativos, meses, pesos="iguais", meta_vol=None):
    ret_d = m[ativos].pct_change()

    def decidir(d):
        h = mensal[mensal.index <= d][ativos]
        if len(h) < meses:
            return pd.Series(dtype=float)
        sma = h.iloc[-meses:].mean()
        dentro = h.iloc[-1] > sma
        vol = ret_d[ret_d.index <= d].iloc[-63:].std() * np.sqrt(252)
        if pesos == "iguais":
            w = pd.Series(1.0 / len(ativos), index=ativos)
        else:                                       # paridade de risco ingênua
            w = (1 / vol) / (1 / vol).sum()
        w = w[dentro]
        if meta_vol and len(w):
            cov = ret_d[ret_d.index <= d].iloc[-63:][w.index].cov() * 252
            vol_cart = float(np.sqrt(w.values @ cov.values @ w.values))
            w = w * min(1.0, meta_vol / vol_cart) if vol_cart > 0 else w
        return w
    return decidir


def fixa(pesos: dict):
    def decidir(d):
        return pd.Series(pesos)
    return decidir


def rodar(nome, familia, params, decidir, m, cdi, imprimir=True, custo=CUSTO, ir=False):
    r = motor.simular(m, decidir, cdi, inicio="2005-01-01", custo=custo, ir=ir)
    met = motor.metricas(r.curva, cdi)
    motor.registrar(familia, nome, {**params, "custo": custo, "ir": ir}, met, {"giro_anual": round(r.giro_anual, 2)})
    if imprimir:
        print(motor.linha_texto(nome, met) + f" | giro {r.giro_anual:.1f}x")
    return r, met


def main():
    m, cdi, cdi_idx, mensal = preparar()
    print(f"Dados: {m.index[0].date()} a {m.index[-1].date()} | testes a partir de 2005-01 | custo {CUSTO:.2%} por lado")
    print("Colunas: retorno ao ano (CDI) | blocos 2005-09, 2010-14, 2015-19, 2020-26 | pior queda | sharpe | critérios 1-4\n")

    print("--- Referências (sem sinal) ---")
    for nome, p in {"100% Ibovespa": {"IBOV": 1}, "100% S&P 500 em reais": {"SPX": 1}, "100% ouro em reais": {"OURO": 1},
                    "1/3 Ibov, 1/3 S&P, 1/3 ouro": {"IBOV": 1/3, "SPX": 1/3, "OURO": 1/3},
                    "1/4 cada (Ibov, S&P, ouro, Treasuries)": {"IBOV": .25, "SPX": .25, "OURO": .25, "TREA": .25},
                    "50% CDI + 50% (1/3 cada)": {"IBOV": 1/6, "SPX": 1/6, "OURO": 1/6}}.items():
        rodar(nome, "referencia", p, fixa(p), m, cdi)

    print("\n--- Família 5: dual momentum ---")
    for ativos in [["IBOV", "SPX", "OURO"], ["IBOV", "SPX", "OURO", "TREA"]]:
        for meses in [6, 9, 12]:
            for n_top in [1, 2]:
                nome = f"DM {'+'.join(a[:3] for a in ativos)} {meses}m top{n_top}"
                rodar(nome, "5_dual_momentum", {"ativos": ativos, "meses": meses, "n_top": n_top},
                      dual_momentum(m, cdi_idx, mensal, ativos, meses, n_top), m, cdi)

    print("\n--- Família 6: tendência por ativo ---")
    for ativos in [["IBOV", "SPX", "OURO"], ["IBOV", "SPX", "OURO", "TREA"]]:
        for meses in [6, 10, 12]:
            for pesos in ["iguais", "risco"]:
                nome = f"TEND {'+'.join(a[:3] for a in ativos)} {meses}m {pesos}"
                rodar(nome, "6_tendencia", {"ativos": ativos, "meses": meses, "pesos": pesos},
                      tendencia(m, cdi_idx, mensal, ativos, meses, pesos), m, cdi)


if __name__ == "__main__":
    main()
