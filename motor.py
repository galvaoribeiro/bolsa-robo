"""
Motor genérico de backtest de carteiras + avaliação pelo PROTOCOLO.md.

simular(precos, decidir, cdi, ...) -> Resultado
  precos : DataFrame diário (colunas = ativos), preço de retorno total em reais.
           NaN = ativo não negocia naquele dia (ainda não listado ou já saiu da bolsa).
  decidir: função(data_decisao) -> Series de pesos alvo (soma <= 1; o resto fica no CDI).
           Só pode usar dados até data_decisao (inclusive).
  Decisão no fechamento do último pregão de cada período; execução no FECHAMENTO do pregão seguinte
  (um dia de atraso, conservador). Ativo que deixou de negociar é vendido pelo último preço.
  Custos por lado sobre o valor negociado. IR opcional: 15% sobre ganho realizado líquido do mês,
  com compensação de prejuízo acumulado (preço médio por ativo).
"""
import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BLOCOS = [("2005-01-01", "2009-12-31"), ("2010-01-01", "2014-12-31"),
          ("2015-01-01", "2019-12-31"), ("2020-01-01", "2026-12-31")]
ARQ_TENTATIVAS = Path(__file__).parent / "resultados" / "tentativas.csv"


@dataclass
class Resultado:
    curva: pd.Series
    pesos: pd.DataFrame            # pesos alvo em cada decisão
    giro_anual: float
    ir_pago: float = 0.0
    extras: dict = field(default_factory=dict)


def datas_rebalanceamento(datas: pd.DatetimeIndex, freq: str = "M") -> list:
    s = pd.Series(datas, index=datas)
    if freq == "M":
        return list(s.groupby([datas.year, datas.month]).last())
    if freq == "W":
        return list(s.groupby(datas.to_period("W")).last())
    raise ValueError(freq)


def simular(precos: pd.DataFrame, decidir, cdi: pd.Series, inicio="2005-01-01", fim=None,
            custo=0.002, freq="M", ir=False) -> Resultado:
    precos = precos.sort_index()
    datas = precos.index[(precos.index >= pd.Timestamp(inicio) - pd.Timedelta(days=40))]
    if fim:
        datas = datas[datas <= pd.Timestamp(fim)]
    px = precos.loc[datas]
    px_marc = px.ffill()                          # marcação: último preço conhecido
    cdi_d = cdi.reindex(datas).ffill().fillna(0).to_numpy()
    rebal = set(d for d in datas_rebalanceamento(datas, freq) if d >= pd.Timestamp(inicio) - pd.Timedelta(days=40))
    ativos = list(px.columns)
    idx = {a: k for k, a in enumerate(ativos)}
    pxv, pxm = px.to_numpy(), px_marc.to_numpy()

    caixa, qtd, pm = 1.0, np.zeros(len(ativos)), np.zeros(len(ativos))
    prejuizo_acum, ganho_mes, ir_total, giro = 0.0, 0.0, 0.0, 0.0
    alvo, curva, registros = None, np.empty(len(datas)), {}
    for i, d in enumerate(datas):
        if i > 0:
            caixa *= 1 + cdi_d[i]
        # executa decisão de ontem
        if alvo is not None:
            preco_exec = pxv[i]
            negociavel = ~np.isnan(preco_exec)
            # ativos sem negociação hoje: mantém a posição (ou vende pelo último preço se saiu da bolsa)
            total = caixa + np.nansum(qtd * pxm[i])
            nova = qtd.copy()
            for a, w in alvo.items():
                k = idx[a]
                if negociavel[k]:
                    nova[k] = w * total / preco_exec[k]
            zerar = [k for k in range(len(ativos)) if qtd[k] > 0 and ativos[k] not in alvo and negociavel[k]]
            for k in zerar:
                nova[k] = 0.0
            # ativo que não negocia mais (NaN daqui em diante) é vendido pelo último preço
            for k in np.where((qtd > 0) & ~negociavel)[0]:
                if np.isnan(pxv[i:min(i + 10, len(datas)), k]).all():
                    nova[k] = 0.0
            delta = nova - qtd
            preco_ref = np.where(negociavel, preco_exec, pxm[i])
            valor_neg = np.nansum(np.abs(delta) * preco_ref)
            # ganho realizado nas vendas
            vendas = delta < 0
            ganho_mes += np.nansum((-delta[vendas]) * (preco_ref[vendas] - pm[vendas]))
            compras = delta > 0
            pm[compras] = np.where(qtd[compras] + delta[compras] > 0,
                                   (qtd[compras] * pm[compras] + delta[compras] * preco_ref[compras])
                                   / (qtd[compras] + delta[compras]), 0)
            caixa -= np.nansum(delta * preco_ref) + valor_neg * custo
            qtd = nova
            pm[qtd == 0] = 0.0
            giro += valor_neg / total if total > 0 else 0
            alvo = None
        # IR mensal (no último pregão do mês)
        if ir and (i == len(datas) - 1 or datas[i + 1].month != d.month):
            liquido = ganho_mes - prejuizo_acum
            if liquido > 0:
                imposto = 0.15 * liquido
                caixa -= imposto
                ir_total += imposto
                prejuizo_acum = 0.0
            else:
                prejuizo_acum = -liquido
            ganho_mes = 0.0
        curva[i] = caixa + np.nansum(qtd * pxm[i])
        # decisão
        if d in rebal and d >= pd.Timestamp(inicio) - pd.Timedelta(days=40):
            w = decidir(d)
            w = w[w > 1e-9] if w is not None and len(w) else pd.Series(dtype=float)
            if w.sum() > 1 + 1e-9:
                w = w / w.sum()
            alvo = w.to_dict()
            registros[d] = w
    curva = pd.Series(curva, index=datas)
    curva = curva[curva.index >= pd.Timestamp(inicio)]
    curva = curva / curva.iloc[0]
    anos = len(curva) / 252
    pesos = pd.DataFrame(registros).T.fillna(0) if registros else pd.DataFrame()
    return Resultado(curva, pesos, giro / anos, ir_total)


# ---------------- métricas e critério ----------------
def cagr(c: pd.Series) -> float:
    c = c.dropna()
    anos = (c.index[-1] - c.index[0]).days / 365.25
    return (c.iloc[-1] / c.iloc[0]) ** (1 / anos) - 1 if anos > 0.2 else float("nan")


def metricas(curva: pd.Series, cdi: pd.Series) -> dict:
    ret = curva.pct_change().dropna()
    rf = cdi.reindex(ret.index).fillna(0)
    exc = ret - rf
    cdi_curva = (1 + rf).cumprod()
    m = {"ao_ano": cagr(curva), "cdi_ao_ano": cagr(cdi_curva), "vol": ret.std() * math.sqrt(252),
         "pior_queda": (curva / curva.cummax() - 1).min(),
         "sharpe": exc.mean() / exc.std() * math.sqrt(252) if exc.std() > 0 else 0.0,
         "n_dias": len(ret), "assimetria": exc.skew(), "curtose": exc.kurt() + 3}
    for k, (a, b) in enumerate(BLOCOS, 1):
        c = curva[a:b]
        m[f"bloco{k}"] = cagr(c) if len(c) > 60 else float("nan")
        m[f"cdi_bloco{k}"] = cagr(cdi_curva[a:b]) if len(c) > 60 else float("nan")
    return m


def sharpe_deflacionado(sr_anual: float, n_dias: int, n_tentativas: int, var_sr_tentativas: float,
                        assimetria: float, curtose: float) -> float:
    """Probabilidade de o Sharpe verdadeiro ser > 0 descontando o número de tentativas
    (Bailey & López de Prado, 2014). Sharpe em base diária internamente."""
    from statistics import NormalDist
    nd = NormalDist()
    sr = sr_anual / math.sqrt(252)
    var_sr = var_sr_tentativas / 252 if var_sr_tentativas > 0 else (1 / n_dias)
    g = 0.5772156649
    n = max(n_tentativas, 2)
    sr0 = math.sqrt(var_sr) * ((1 - g) * nd.inv_cdf(1 - 1 / n) + g * nd.inv_cdf(1 - 1 / (n * math.e)))
    denom = math.sqrt(max(1e-12, 1 - assimetria * sr + (curtose - 1) / 4 * sr ** 2))
    return nd.cdf((sr - sr0) * math.sqrt(n_dias - 1) / denom)


def criterios_basicos(m: dict) -> dict:
    """Critérios 1–4 do protocolo que dependem só da curva (robustez é avaliada à parte)."""
    blocos_acima = sum(1 for k in range(1, 5) if m[f"bloco{k}"] > m[f"cdi_bloco{k}"])
    return {
        "c1_cdi_mais_5": m["ao_ano"] >= m["cdi_ao_ano"] + 0.05,
        "c2_blocos": blocos_acima >= 3 and m["bloco4"] > m["cdi_bloco4"],
        "c3_queda_30": m["pior_queda"] >= -0.30,
        "c4_sharpe_05": m["sharpe"] >= 0.5,
    }


def registrar(familia: str, nome: str, params: dict, m: dict, extra: dict | None = None):
    ARQ_TENTATIVAS.parent.mkdir(exist_ok=True)
    novo = not ARQ_TENTATIVAS.exists()
    c = criterios_basicos(m)
    linha = {"quando": datetime.now().strftime("%Y-%m-%d %H:%M"), "familia": familia, "nome": nome,
             "params": json.dumps(params, ensure_ascii=False),
             **{k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()},
             **c, "passa_1a4": all(c.values()), **(extra or {})}
    with open(ARQ_TENTATIVAS, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linha.keys()))
        if novo:
            w.writeheader()
        w.writerow(linha)
    return linha


def linha_texto(nome: str, m: dict) -> str:
    bl = " ".join(f"{m[f'bloco{k}']:+6.1%}" for k in range(1, 5))
    c = criterios_basicos(m)
    marca = "PASSA" if all(c.values()) else "".join("x" if not v else "." for v in c.values())
    return (f"{nome:42s} | {m['ao_ano']:+6.1%} (CDI {m['cdi_ao_ano']:+5.1%}) | blocos {bl} | "
            f"queda {m['pior_queda']:+6.1%} | sharpe {m['sharpe']:+.2f} | {marca}")
