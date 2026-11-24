"""
Backtest de momentum mensal em ações da B3.

Regra principal (decidida no último pregão do mês, executada na abertura do 1º pregão do mês seguinte):
  1. Para cada ação, calcula o retorno dos últimos 12 meses, ignorando o último mês
     (o último mês costuma "devolver" parte do movimento, por isso fica de fora).
  2. Ordena e escolhe as 5 maiores.
  3. Filtro absoluto: só compra a ação se esse retorno for MAIOR que o CDI do mesmo período.
     A vaga que sobra fica no CDI. Em mercado de queda, a carteira vai quase toda para o CDI.
  4. Divide igualmente entre as vagas e mantém até o mês seguinte.

Variações testadas (só para ver se o resultado é robusto, não para escolher a melhor):
  janela de 6 meses, 3 ações em vez de 5, e sem o filtro absoluto.

Universos:
  - "15 sobreviventes": as mesmas ações do backtest de swing trade
  - "21 com as que quebraram": as 15 + Americanas, Oi, Casas Bahia, CVC, IRB, Magalu (reduz o viés)

Uso: python backtest_momentum.py
"""
import numpy as np
import pandas as pd

import dados
from backtest_swing import CUSTO, ESTRESSE, TICKERS, metricas

CONFIGS = {
    "12m, 5 ações, c/ filtro (principal)": dict(meses=12, n=5, filtro=True),
    "6m, 5 ações, c/ filtro": dict(meses=6, n=5, filtro=True),
    "12m, 3 ações, c/ filtro": dict(meses=12, n=3, filtro=True),
    "12m, 5 ações, SEM filtro": dict(meses=12, n=5, filtro=False),
}


def simular(abert: pd.DataFrame, fech: pd.DataFrame, cdi: pd.Series, meses: int, n: int, filtro: bool):
    datas = fech.index
    cdi_d = cdi.reindex(datas).fillna(0)
    cdi_acum = (1 + cdi_d).cumprod()
    fim_mes = set(fech.groupby([datas.year, datas.month]).tail(1).index)
    fim_mes.discard(datas[-1])                 # último dia dos dados: mês ainda não terminou
    dias_mes = 21

    caixa, qtd = 1.0, pd.Series(0.0, index=fech.columns)
    alvo = None
    curva, carteiras, giro = [], [], 0.0
    for i, d in enumerate(datas):
        if i > 0:
            caixa *= 1 + cdi_d.iloc[i]
        # executa o rebalanceamento decidido ontem, na abertura
        if alvo is not None:
            px = abert.iloc[i].fillna(fech.iloc[i - 1])
            total = caixa + (qtd * px).sum()
            novo = (alvo * total / px).fillna(0)
            negociado = ((novo - qtd).abs() * px).sum()
            giro += negociado / total
            caixa = total - (novo * px).sum() - negociado * CUSTO
            qtd, alvo = novo, None
        valor = caixa + (qtd * fech.iloc[i].fillna(0)).sum()
        curva.append(valor)

        # decisão no último pregão do mês
        ini = i - meses * dias_mes
        if d in fim_mes and ini >= 0:
            ret = fech.iloc[i - dias_mes] / fech.iloc[ini] - 1        # 12 meses, sem o último
            ret = ret.dropna()
            escolhidas = ret.sort_values(ascending=False).head(n)
            if filtro:
                cdi_periodo = cdi_acum.iloc[i - dias_mes] / cdi_acum.iloc[ini] - 1
                escolhidas = escolhidas[escolhidas > cdi_periodo]
            alvo = pd.Series(0.0, index=fech.columns)
            alvo[escolhidas.index] = 1.0 / n                           # vaga vazia = CDI
            carteiras.append((d.date(), list(escolhidas.index.str[:-3])))

    anos = len(datas) / 252
    return pd.Series(curva, index=datas), carteiras, giro / anos


def main():
    cdi = dados.cdi()
    universos = {"15 sobreviventes": TICKERS, "21 com as que quebraram": TICKERS + ESTRESSE}
    bova = dados.precos(["BOVA11.SA"])["BOVA11.SA"]["Close"]

    for nome_u, tickers in universos.items():
        p = dados.precos(tickers)
        fech = pd.DataFrame({t: p[t]["Close"] for t in tickers}).sort_index()
        abert = pd.DataFrame({t: p[t]["Open"] for t in tickers}).reindex(fech.index)
        fech = fech.ffill(limit=5)
        inicio = fech.index[12 * 21 + 1]                               # 1ª decisão possível

        curvas = {}
        for nome_c, cfg in CONFIGS.items():
            curva, carteiras, giro = simular(abert, fech, cdi, **cfg)
            curvas[nome_c] = curva[inicio:]
            if "principal" in nome_c:
                principal_carteiras, principal_giro = carteiras, giro
        ew = fech[inicio:].pct_change().mean(axis=1).fillna(0)
        curvas["Comprar e segurar (todas, peso igual)"] = (1 + ew).cumprod()
        curvas["BOVA11"] = bova.reindex(fech.index).ffill()[inicio:]
        curvas["CDI"] = (1 + cdi.reindex(fech.index).fillna(0)[inicio:]).cumprod()

        datas = curvas["CDI"].index
        meio = datas[len(datas) // 2]
        print(f"\n######## Universo: {nome_u} | {datas[0].date()} a {datas[-1].date()} "
              f"(metades divididas em {meio.date()}) ########")
        print(f"{'':40s} | {'ao ano':>7s} | {'1ª met.':>7s} | {'2ª met.':>7s} | {'pior queda':>10s} | sharpe")
        for k, c in curvas.items():
            c = c.dropna()
            m, m1, m2 = metricas(c, cdi), metricas(c[:meio], cdi), metricas(c[meio:], cdi)
            print(f"{k:40s} | {m['ao_ano']:+7.1%} | {m1['ao_ano']:+7.1%} | {m2['ao_ano']:+7.1%} | "
                  f"{m['pior_queda']:+10.1%} | {m['sharpe']:+.2f}")

        vazias = sum(1 for _, c in principal_carteiras if len(c) == 0)
        print(f"\nPrincipal: giro de {principal_giro:.1f}x o patrimônio por ano | "
              f"{vazias} de {len(principal_carteiras)} meses 100% no CDI")
        print("Últimas carteiras (decisão no fim do mês):")
        for d, c in principal_carteiras[-3:]:
            print(f"   {d}: {', '.join(c) if c else 'tudo no CDI'}")


if __name__ == "__main__":
    main()
