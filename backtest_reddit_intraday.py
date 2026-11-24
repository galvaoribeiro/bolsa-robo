"""
Estratégia do Reddit (u/Square-Buy-7403) no gráfico de minuto, com adaptações para limitar a perda.

Regras (definidas ANTES de ver o resultado):
  - Novas entradas só entre 10:30 e 16:00. Tudo é zerado às 16:45 (day trade, nada de um dia para o outro).
  - Entrada: IFR(14) do gráfico < 30 e preço pelo menos 0,5% abaixo da máxima do dia -> compra 1/5 do capital.
  - Preço médio para baixo: se cair mais 0,5% abaixo da última compra e IFR < 30, compra mais 1/5 (até 5).
  - Alvo: preço médio + ALVO (ordem limitada; só conta como executada se o preço passar 1 centavo do alvo).
  - Adaptações anti-perda grande:
      1) stop da posição inteira em 1,5% abaixo do preço médio
      2) zeragem obrigatória às 16:45 (elimina abertura muito abaixo no dia seguinte, o "caso Americanas")
      3) depois de um stop, aquela ação não opera mais no dia
  - Comparação: versão ORIGINAL, sem stop e levando a posição de um dia para o outro.
  - Custo: 0,05% por lado (taxas de day trade da B3 + diferença compra/venda). IR de 20% NÃO incluído.
  - Sinal no fechamento da barra, execução na abertura da barra seguinte.

Uso: python backtest_reddit_intraday.py            (1 minuto, ~30 dias)
     python backtest_reddit_intraday.py 5m         (5 minutos, ~60 dias)
"""
import sys

import numpy as np
import pandas as pd

import dados
from backtest_swing import TICKERS, ifr

CUSTO = 0.0005
INICIO_ENTRADAS, FIM_ENTRADAS, ZERAGEM = "10:30", "16:00", "16:45"

VERSOES = {
    "Adaptada, alvo 0,3% (principal)": dict(alvo=0.003, stop=0.015, zerar=True),
    "Adaptada, alvo 0,1%": dict(alvo=0.001, stop=0.015, zerar=True),
    "Original, alvo 0,3% (sem stop)": dict(alvo=0.003, stop=None, zerar=False),
}


def simular(df: pd.DataFrame, cdi: pd.Series, alvo: float, stop: float | None, zerar: bool):
    df = df.copy()
    dia = df.index.normalize()
    hora = df.index.strftime("%H:%M")
    # IFR e máxima do dia calculados dentro de cada dia (sem misturar com o dia anterior)
    df["ifr"] = df.groupby(dia)["Close"].transform(lambda s: ifr(s, 14))
    df["max_dia"] = df.groupby(dia)["High"].cummax()
    o, h, l, c = (df[k].to_numpy() for k in ["Open", "High", "Low", "Close"])
    rsi, mx = df["ifr"].to_numpy(), df["max_dia"].to_numpy()
    dia_arr = dia.to_numpy()
    taxa = cdi.reindex(dia).ffill().fillna(0).to_numpy()

    caixa, qtd, custo_total, partes, ultima = 1.0, 0.0, 0.0, 0, 0.0
    ordem, bloqueado_dia, entrada_i, pior = None, None, -1, 0.0
    curva, ops = np.empty(len(df)), []

    def vender(i, preco, motivo):
        nonlocal caixa, qtd, custo_total, partes
        valor = qtd * preco * (1 - CUSTO)
        ops.append({"entrada": df.index[entrada_i], "saida": df.index[i], "partes": partes,
                    "minutos": (df.index[i] - df.index[entrada_i]).total_seconds() / 60,
                    "resultado": valor / custo_total - 1, "pior_flutuante": pior, "motivo": motivo})
        caixa += valor
        qtd, custo_total, partes = 0.0, 0.0, 0

    for i in range(len(df)):
        novo_dia = i == 0 or dia_arr[i] != dia_arr[i - 1]
        if novo_dia:
            caixa *= 1 + taxa[i]
            ordem = None                                   # ordens não passam de um dia para o outro

        # 1) executa ordem de compra decidida na barra anterior
        if ordem == "comprar":
            valor = caixa / (5 - partes)
            qtd += valor * (1 - CUSTO) / o[i]
            custo_total += valor
            caixa -= valor
            if partes == 0:
                entrada_i, pior = i, 0.0
            partes += 1
            ultima = o[i]
        ordem = None

        # 2) ordens que ficam no livro: alvo e stop
        if qtd > 0:
            medio = custo_total / qtd
            preco_alvo = medio * (1 + alvo)
            if h[i] >= preco_alvo + 0.01:
                vender(i, max(o[i], preco_alvo), "alvo")
            elif stop is not None and l[i] <= medio * (1 - stop):
                vender(i, min(o[i], medio * (1 - stop)), "stop")
                bloqueado_dia = dia_arr[i]
        if qtd > 0:
            pior = min(pior, qtd * c[i] / custo_total - 1)

        # 3) zeragem obrigatória
        if zerar and qtd > 0 and hora[i] >= ZERAGEM:
            vender(i, o[i], "zeragem")

        # 4) decisão no fechamento da barra
        pode_entrar = INICIO_ENTRADAS <= hora[i] < FIM_ENTRADAS and bloqueado_dia != dia_arr[i]
        if pode_entrar and rsi[i] < 30:
            if qtd == 0 and c[i] <= mx[i] * 0.995:
                ordem = "comprar"
            elif 0 < partes < 5 and c[i] <= ultima * 0.995:
                ordem = "comprar"

        curva[i] = caixa + qtd * c[i]

    if qtd > 0:
        vender(len(df) - 1, c[-1], "aberta_no_fim")
        curva[-1] = caixa
    return pd.Series(curva, index=df.index), ops


def main():
    intervalo = sys.argv[1] if len(sys.argv) > 1 else "1m"
    cdi = dados.cdi()
    barras = {t: dados.intraday(t, intervalo) for t in TICKERS}
    dias = sorted(set().union(*[set(b.index.normalize()) for b in barras.values()]))
    cdi_periodo = (1 + cdi.reindex(pd.DatetimeIndex(dias)).ffill().fillna(0)).prod() - 1
    print(f"Gráfico de {intervalo} | {len(dias)} pregões: {dias[0].date()} a {dias[-1].date()} | "
          f"15 ações, uma subconta para cada | CDI no período: {cdi_periodo:+.2%}")

    for nome, cfg in VERSOES.items():
        curvas, ops = [], []
        for t, b in barras.items():
            cur, o = simular(b, cdi, **cfg)
            curvas.append(cur.groupby(cur.index.normalize()).last())
            ops += [dict(x, acao=t[:-3]) for x in o]
        diaria = pd.concat(curvas, axis=1).ffill().fillna(1.0).mean(axis=1)
        r = pd.DataFrame(ops)
        g, p = r[r.resultado > 0].resultado, r[r.resultado <= 0].resultado
        fator = g.sum() / -p.sum() if len(p) and p.sum() < 0 else float("inf")
        ret_dia = diaria.pct_change().dropna()
        print(f"\n=== {nome} ===")
        print(f"Carteira: total {diaria.iloc[-1] - 1:+.2%} (CDI {cdi_periodo:+.2%}) | "
              f"dias no positivo {(ret_dia > 0).mean():.0%} | pior dia {ret_dia.min():+.2%} | "
              f"pior queda {(diaria / diaria.cummax() - 1).min():+.2%}")
        print(f"Operações: {len(r)} | acerto {len(g) / len(r):.0%} | ganho médio {g.mean():+.2%} | "
              f"perda média {p.mean() if len(p) else 0:+.2%} | fator de lucro {fator:.2f}")
        print(f"   pior operação {r.resultado.min():+.2%} | pior perda flutuante {r.pior_flutuante.min():+.2%} | "
              f"duração média {r.minutos.mean():.0f} min | média de compras por operação {r.partes.mean():.1f}")
        print(f"   saídas: {r.motivo.value_counts().to_dict()}")
        ac = r.groupby("acao").resultado.apply(lambda s: (1 + s).prod() - 1).sort_values()
        print(f"   pior ação: {ac.index[0]} {ac.iloc[0]:+.2%} | melhor: {ac.index[-1]} {ac.iloc[-1]:+.2%}")
        tag = nome.split(",")[0].lower() + "_" + nome.split("alvo ")[1].split("%")[0].replace(",", "")
        r.to_csv(f"resultados/operacoes_reddit_intraday_{intervalo}_{tag}.csv", index=False)


if __name__ == "__main__":
    main()
