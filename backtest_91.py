"""
Backtest do Setup 9.1 (Larry Williams) no gráfico diário — só compra.

Regras (definidas ANTES de ver o resultado):
  - MME9: média móvel exponencial de 9 períodos do fechamento.
  - Sinal: a MME9 vinha caindo (ou estável) e virou para cima no fechamento -> candle de referência.
  - Entrada: ordem stop de compra na máxima do candle de referência, para o pregão seguinte.
    Se não executar e a MME9 continuar subindo, o candle mais recente vira a nova referência
    (entrada na máxima dele, stop na mínima dele). Se a MME9 virar para baixo, cancela.
  - Stop inicial: mínima do candle de referência.
  - Saída: quando a MME9 vira para baixo, ordem stop de venda na mínima desse candle; enquanto
    continuar caindo, a ordem vai para a mínima do candle mais recente. Se voltar a subir, cancela
    (o stop inicial continua valendo).
  - Se a entrada e o stop forem atingidos no mesmo dia, considera que o stop foi atingido (pessimista).

Mesmas regras de teste dos outros backtests: custo 0,10% por lado, CDI real no caixa,
uma subconta por ação, comparação com CDI e comprar e segurar, duas metades.

Uso: python backtest_91.py
"""
import numpy as np
import pandas as pd

import dados
from backtest_swing import CUSTO, ESTRESSE, TICKERS, metricas, resumo_operacoes


def simular(df: pd.DataFrame, cdi: pd.Series):
    o, h, l, c = (df[k].to_numpy() for k in ["Open", "High", "Low", "Close"])
    mme = df["Close"].ewm(span=9, adjust=False).mean().to_numpy()
    taxa = cdi.reindex(df.index).ffill().fillna(0).to_numpy()

    caixa, qtd, custo_total = 1.0, 0.0, 0.0
    ordem_compra = stop_pendente = None
    stop = saida = None
    entrada_i, pior_flutuante = -1, 0.0
    curva, ops = np.empty(len(df)), []

    def vender(i, preco, motivo):
        nonlocal caixa, qtd, custo_total, stop, saida
        valor = qtd * preco * (1 - CUSTO)
        ops.append({"entrada": df.index[entrada_i], "saida": df.index[i], "dias": i - entrada_i,
                    "resultado": valor / custo_total - 1, "pior_flutuante": pior_flutuante,
                    "motivo": motivo})
        caixa += valor
        qtd, custo_total, stop, saida = 0.0, 0.0, None, None

    for i in range(len(df)):
        if i > 0:
            caixa *= 1 + taxa[i]

        # --- durante o pregão: ordens stop que estão na corretora ---
        if qtd == 0 and ordem_compra is not None and h[i] >= ordem_compra:
            preco = max(o[i], ordem_compra)
            custo_total, qtd, caixa = caixa, caixa * (1 - CUSTO) / preco, 0.0
            entrada_i, stop, saida, pior_flutuante = i, stop_pendente, None, 0.0
            ordem_compra = None
            if l[i] <= stop:                       # entrou e estopou no mesmo dia
                vender(i, stop, "stop_mesmo_dia")
        elif qtd > 0:
            gatilho = max(stop, saida) if saida is not None else stop
            if l[i] <= gatilho:
                vender(i, min(o[i], gatilho), "saida_mme" if saida is not None and saida >= stop else "stop")

        if qtd > 0:
            pior_flutuante = min(pior_flutuante, qtd * c[i] / custo_total - 1)

        # --- no fechamento: ajusta as ordens para amanhã ---
        if i >= 2:
            subindo = mme[i] > mme[i - 1]
            virou_cima = subindo and mme[i - 1] <= mme[i - 2]
            if qtd == 0:
                if virou_cima or (ordem_compra is not None and subindo):
                    ordem_compra, stop_pendente = h[i], l[i]
                elif not subindo:
                    ordem_compra = None
            else:
                saida = l[i] if mme[i] < mme[i - 1] else None

        curva[i] = caixa + qtd * c[i]

    if qtd > 0:
        vender(len(df) - 1, c[-1], "aberta_no_fim")
        curva[-1] = caixa
    return pd.Series(curva, index=df.index), ops


def main():
    cdi = dados.cdi()
    universos = {"15 sobreviventes": TICKERS, "21 com as que quebraram": TICKERS + ESTRESSE,
                 "Só BOVA11": ["BOVA11.SA"]}
    for nome_u, tickers in universos.items():
        p = dados.precos(tickers)
        datas = pd.DatetimeIndex(sorted(set().union(*[df.index for df in p.values()])))
        datas = datas[datas >= "2011-01-11"]           # mesmo início do teste de momentum

        def carteira(series):
            cols = []
            for s in series:
                s = s.reindex(datas).ffill()
                s = s / s.dropna().iloc[0]
                cols.append(s.fillna(1.0))
            return pd.concat(cols, axis=1).mean(axis=1)

        sims = {t: simular(p[t], cdi) for t in tickers}
        curvas = {
            "Setup 9.1": carteira([s[0] for s in sims.values()]),
            "Comprar e segurar": carteira([p[t]["Close"] for t in tickers]),
            "CDI": (1 + cdi.reindex(datas).fillna(0)).cumprod(),
        }
        meio = datas[len(datas) // 2]
        print(f"\n######## {nome_u} | {datas[0].date()} a {datas[-1].date()} "
              f"(metades em {meio.date()}) ########")
        print(f"{'':20s} | {'ao ano':>7s} | {'1ª met.':>7s} | {'2ª met.':>7s} | {'pior queda':>10s} | sharpe")
        for k, c in curvas.items():
            m, m1, m2 = metricas(c, cdi), metricas(c[:meio], cdi), metricas(c[meio:], cdi)
            print(f"{k:20s} | {m['ao_ano']:+7.1%} | {m1['ao_ano']:+7.1%} | {m2['ao_ano']:+7.1%} | "
                  f"{m['pior_queda']:+10.1%} | {m['sharpe']:+.2f}")
        if len(tickers) > 1:
            # dependência de uma única ação: refaz sem a subconta que mais rendeu
            finais = {t: s[0].reindex(datas).ffill().iloc[-1] / s[0].reindex(datas).ffill().dropna().iloc[0]
                      for t, s in sims.items()}
            melhor = max(finais, key=finais.get)
            c = carteira([s[0] for t, s in sims.items() if t != melhor])
            m, m1, m2 = metricas(c, cdi), metricas(c[:meio], cdi), metricas(c[meio:], cdi)
            print(f"{'9.1 sem ' + melhor[:-3]:20s} | {m['ao_ano']:+7.1%} | {m1['ao_ano']:+7.1%} | "
                  f"{m2['ao_ano']:+7.1%} | {m['pior_queda']:+10.1%} | {m['sharpe']:+.2f}"
                  f"   <- sem a ação que mais rendeu ({finais[melhor]:.0f}x)")
        ops = [dict(x, acao=t) for t, s in sims.items() for x in s[1] if x["entrada"] >= datas[0]]
        r = pd.DataFrame(ops)
        dias_comprado = r.dias.sum() / (len(tickers) * len(datas))
        print(f"Operações: {resumo_operacoes(ops)}")
        print(f"   tempo comprado: {dias_comprado:.0%} | motivos de saída: {r.motivo.value_counts().to_dict()}")
        if nome_u.startswith("21"):
            r.to_csv("resultados/operacoes_setup91.csv", index=False)


if __name__ == "__main__":
    main()
