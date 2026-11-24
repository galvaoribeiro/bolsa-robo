"""
Backtest de swing trade em ações da B3 — compara duas estratégias com as mesmas regras de teste.

A) "correcao" — compra na correção dentro de tendência de alta, COM stop
   - Sinal no fechamento: preço acima da MM200 (tendência de alta) e IFR(2) < 10 (caiu forte em poucos dias)
   - Compra na abertura do dia seguinte
   - Sai na abertura seguinte quando o fechamento passa da MM5 (recuperou) ou após 10 pregões
   - Stop de 8% abaixo da entrada, registrado na corretora (executa no próprio dia se a mínima tocar)

B) "reddit" — adaptação diária da estratégia do post r/GrokBot (u/Square-Buy-7403)
   - Capital dividido em 5 partes; compra 1 parte quando IFR(14) < 30 (sobrevendido)
   - Se cair mais 5% abaixo da última compra e seguir sobrevendido, compra mais 1 parte (até 5)
   - Vende tudo quando o preço sobe 1% acima do preço médio. SEM STOP.
   - O original opera no gráfico de 1 minuto e vende a +US$0,02; aqui é no diário, que é o que
     cabe na sua rotina. O alvo de +1% é generoso: com +0,1% os custos comeriam tudo.

Regras do teste (iguais para as duas):
   - Sinal com o fechamento de hoje, execução na abertura de amanhã (nada de olhar o futuro)
   - Custo de 0,10% por compra ou venda (emolumentos + corretagem + derrapagem)
   - Cada ação tem uma "subconta" com o mesmo capital; dinheiro parado rende CDI real
   - Comparação com CDI e com comprar e segurar as mesmas ações; período dividido em 2 metades

Uso: python backtest_swing.py
"""
import numpy as np
import pandas as pd

import dados

ACOES = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "ITSA4",
         "B3SA3", "SUZB3", "GGBR4", "LREN3", "RENT3", "EQTL3", "CMIG4"]
TICKERS = [a + ".SA" for a in ACOES]
CUSTO = 0.001


# ---------- indicadores ----------
def ifr(close: pd.Series, n: int) -> pd.Series:
    """Índice de Força Relativa (RSI) de Wilder."""
    d = close.diff()
    ganho = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    perda = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + ganho / perda)


# ---------- simulação de uma ação ----------
def simular(df: pd.DataFrame, cdi: pd.Series, estrategia: str):
    """Devolve (curva de patrimônio diária da subconta, lista de operações)."""
    o, h, l, c = (df[k].to_numpy() for k in ["Open", "High", "Low", "Close"])
    mm200 = df["Close"].rolling(200).mean().to_numpy()
    mm5 = df["Close"].rolling(5).mean().to_numpy()
    ifr2 = ifr(df["Close"], 2).to_numpy()
    ifr14 = ifr(df["Close"], 14).to_numpy()
    taxa = cdi.reindex(df.index).ffill().fillna(0).to_numpy()

    caixa, qtd, custo_total = 1.0, 0.0, 0.0      # custo_total = dinheiro gasto na posição
    partes, ultima_compra, entrada_i, stop = 0, 0.0, -1, 0.0
    pior_flutuante = 0.0
    ordem = None                                  # ordem para a abertura de amanhã
    curva, operacoes = np.empty(len(df)), []

    def vender(i, preco, motivo):
        nonlocal caixa, qtd, custo_total, partes
        valor = qtd * preco * (1 - CUSTO)
        operacoes.append({"entrada": df.index[entrada_i], "saida": df.index[i],
                          "dias": i - entrada_i, "resultado": valor / custo_total - 1,
                          "partes": partes, "pior_flutuante": pior_flutuante, "motivo": motivo})
        caixa += valor
        qtd, custo_total, partes = 0.0, 0.0, 0

    for i in range(len(df)):
        if i > 0:
            caixa *= 1 + taxa[i]                  # caixa rende CDI

        # 1) executa a ordem decidida ontem, na abertura
        if ordem == "comprar_tudo":
            valor = caixa
            qtd, custo_total, caixa = valor * (1 - CUSTO) / o[i], valor, 0.0
            entrada_i, stop, partes, pior_flutuante = i, o[i] * 0.92, 1, 0.0
        elif ordem == "comprar_parte":
            valor = min(caixa, caixa / (5 - partes))  # divide o caixa restante pelas partes que faltam
            qtd += valor * (1 - CUSTO) / o[i]
            custo_total += valor
            caixa -= valor
            if partes == 0:
                entrada_i, pior_flutuante = i, 0.0
            partes += 1
            ultima_compra = o[i]
        elif ordem == "vender" and qtd > 0:
            vender(i, o[i], "saida")
        ordem = None

        # 2) ordens que ficam na corretora durante o dia (stop / alvo)
        if qtd > 0 and estrategia == "correcao" and l[i] <= stop:
            vender(i, min(o[i], stop), "stop")
        if qtd > 0 and estrategia == "reddit":
            alvo = custo_total / qtd * (1 + 0.01)
            if h[i] >= alvo:
                vender(i, max(o[i], alvo), "alvo")

        if qtd > 0:
            pior_flutuante = min(pior_flutuante, qtd * c[i] / custo_total - 1)

        # 3) decisão com o fechamento (vale para amanhã)
        if i >= 200:
            if estrategia == "correcao":
                if qtd == 0 and c[i] > mm200[i] and ifr2[i] < 10:
                    ordem = "comprar_tudo"
                elif qtd > 0 and (c[i] > mm5[i] or i - entrada_i >= 10):
                    ordem = "vender"
            else:
                if qtd == 0 and ifr14[i] < 30:
                    ordem = "comprar_parte"
                elif 0 < partes < 5 and ifr14[i] < 30 and c[i] <= ultima_compra * 0.95:
                    ordem = "comprar_parte"

        curva[i] = caixa + qtd * c[i]

    if qtd > 0:                                   # posição ainda aberta no fim: registra no preço atual
        vender(len(df) - 1, c[-1], "aberta_no_fim")
        curva[-1] = caixa
    return pd.Series(curva, index=df.index), operacoes


# ---------- métricas ----------
def metricas(curva: pd.Series, cdi: pd.Series) -> dict:
    ret = curva.pct_change().dropna()
    anos = len(ret) / 252
    cagr = (curva.iloc[-1] / curva.iloc[0]) ** (1 / anos) - 1
    excesso = ret - cdi.reindex(ret.index).fillna(0)
    return {"ao_ano": cagr, "vol": ret.std() * np.sqrt(252),
            "pior_queda": (curva / curva.cummax() - 1).min(),
            "sharpe": excesso.mean() / ret.std() * np.sqrt(252)}


def resumo_operacoes(ops: list[dict]) -> str:
    if not ops:
        return "nenhuma operação"
    r = pd.DataFrame(ops)
    g, p = r[r.resultado > 0].resultado, r[r.resultado <= 0].resultado
    fator = g.sum() / -p.sum() if len(p) and p.sum() else float("inf")
    return (f"{len(r)} operações | acerto {len(g) / len(r):.0%} | ganho médio {g.mean():+.1%} | "
            f"perda média {p.mean() if len(p) else 0:+.1%} | fator de lucro {fator:.2f}\n"
            f"   duração média {r.dias.mean():.0f} pregões (máx {r.dias.max()}) | "
            f"pior operação {r.resultado.min():+.1%} | pior perda flutuante {r.pior_flutuante.min():+.1%}")


def main():
    precos = dados.precos(TICKERS)
    cdi = dados.cdi()
    datas = sorted(set().union(*[df.index for df in precos.values()]))
    datas = pd.DatetimeIndex(datas)
    datas = datas[datas >= precos[TICKERS[0]].index[200]]     # começa quando já há MM200

    def carteira(curvas: dict[str, pd.Series]) -> pd.Series:
        # cada subconta começa em 1 na primeira data em comum; antes disso, rende CDI
        alinhadas = []
        for s in curvas.values():
            s = s.reindex(datas).ffill()
            s = s / s.dropna().iloc[0]
            alinhadas.append(s.fillna(1.0))
        return pd.concat(alinhadas, axis=1).mean(axis=1)

    resultados, todas_ops = {}, {}
    for est in ["correcao", "reddit"]:
        curvas, ops = {}, []
        for t in TICKERS:
            curvas[t], o = simular(precos[t], cdi, est)
            ops += [dict(x, acao=t) for x in o]
        resultados[est] = carteira(curvas)
        todas_ops[est] = ops
    resultados["comprar_segurar"] = carteira({t: precos[t]["Close"] for t in TICKERS})
    resultados["cdi"] = (1 + cdi.reindex(datas).fillna(0)).cumprod()

    nomes = {"correcao": "A) Correção c/ stop", "reddit": "B) Reddit (média p/ baixo)",
             "comprar_segurar": "Comprar e segurar", "cdi": "CDI"}
    meio = datas[len(datas) // 2]
    for titulo, ini, fim in [("Período completo", datas[0], datas[-1]),
                             ("1ª metade", datas[0], meio), ("2ª metade", meio, datas[-1])]:
        print(f"\n=== {titulo}: {ini.date()} a {fim.date()} ===")
        for k, nome in nomes.items():
            m = metricas(resultados[k][ini:fim], cdi)
            print(f"{nome:27s} | ao ano {m['ao_ano']:+6.1%} | vol {m['vol']:5.1%} | "
                  f"pior queda {m['pior_queda']:+6.1%} | sharpe {m['sharpe']:+.2f}")

    print("\n=== Operações (todas as 15 ações, período completo) ===")
    for est in ["correcao", "reddit"]:
        print(f"{nomes[est]}:\n   {resumo_operacoes(todas_ops[est])}")
        pd.DataFrame(todas_ops[est]).to_csv(f"resultados/operacoes_{est}.csv", index=False)

    estresse(cdi)


# Ações que despencaram. A lista principal só tem empresas que sobreviveram bem
# (viés de sobrevivência); aqui cada ação é operada sozinha com a conta inteira,
# como o autor do post faz ("one stock at a time").
ESTRESSE = ["AMER3.SA", "OIBR3.SA", "BHIA3.SA", "CVCB3.SA", "IRBR3.SA", "MGLU3.SA"]


def estresse(cdi: pd.Series):
    print("\n=== Teste de estresse: uma ação por conta, com a conta inteira nela ===")
    print("(total = quanto a conta rendeu; compare com o CDI do mesmo período)")
    precos = dados.precos(ESTRESSE)
    for t in ESTRESSE:
        p = precos[t]
        ini = p.index[200]
        cdi_total = (1 + cdi[ini:]).prod() - 1
        linha = f"{t[:-3]:6s} ação {p.Close.iloc[-1] / p.Close.iloc[200] - 1:+5.0%} | CDI {cdi_total:+5.0%}"
        for est, rot in [("correcao", "A"), ("reddit", "B")]:
            curva, ops = simular(p, cdi, est)
            c = curva[ini:]
            pior_op = min(o["resultado"] for o in ops)
            linha += (f" | {rot}: total {c.iloc[-1] / c.iloc[0] - 1:+5.0%}, "
                      f"pior queda {(c / c.cummax() - 1).min():+4.0%}, pior operação {pior_op:+4.0%}")
        print(linha)


if __name__ == "__main__":
    main()
