"""
Painel de ações da B3 SEM viés de sobrevivência, para as famílias 1–4 do PROTOCOLO.md.

Como é montado:
  1. COTAHIST (B3): todas as ações negociadas, inclusive as que saíram da bolsa. Dá o volume
     financeiro de cada dia (para o filtro de liquidez) e o preço bruto (sem ajuste).
  2. Para cada código que algum dia esteve entre as 200 mais negociadas, busca o preço ajustado
     no Yahoo (inclui proventos e desdobramentos). Usa o Yahoo só nos dias em que AQUELE código
     negociou na B3 (evita contar duas vezes empresas que trocaram de código).
  3. Retorno diário = retorno do Yahoo; se o Yahoo não tem o código ou diverge demais do preço
     oficial (erro de dados), usa o retorno bruto da B3 corrigido para desdobramento/grupamento.
     Nesses trechos não há proventos (viés conservador).

Saída (dados/painel/): retorno.parquet (data × código, retorno total diário, NaN = não negociou),
volume.parquet (volume financeiro diário em R$), fonte.parquet (proporção de retornos vindos do Yahoo).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import dados_b3

PASTA = Path(__file__).parent / "dados" / "painel"
FATORES = np.array([1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100, 200, 500, 1000], float)


def candidatos(cot: pd.DataFrame, top: int = 200) -> list[str]:
    """Códigos que estiveram entre os `top` mais negociados (média de 63 pregões) em algum fim de mês."""
    vol = cot.pivot_table(index="data", columns="codigo", values="volume", aggfunc="sum")
    media = vol.fillna(0).rolling(63, min_periods=40).mean()
    fim_mes = media.groupby([media.index.year, media.index.month]).tail(1)
    escolhidos = set()
    for _, linha in fim_mes.iterrows():
        escolhidos |= set(linha.nlargest(top).index)
    return sorted(escolhidos)


def retorno_bruto_corrigido(df: pd.DataFrame) -> pd.Series:
    """Retorno diário pelo preço oficial, desfazendo desdobramentos/grupamentos detectados
    (salto de preço ≈ fator 'redondo' e quantidade negociada mudando na proporção inversa)."""
    df = df.set_index("data").sort_index()
    p, q = df["fechamento"], df["quantidade"].astype(float)
    r = p / p.shift(1)
    for i in np.where((r > 1.45) | (r < 0.70))[0]:
        razao = r.iloc[i]
        alvo = razao if razao > 1 else 1 / razao
        k = FATORES[np.argmin(np.abs(FATORES / alvo - 1))]
        if abs(k / alvo - 1) > 0.12:
            continue
        antes = q.iloc[max(0, i - 20):i].median()
        depois = q.iloc[i:i + 20].median()
        if antes <= 0 or depois <= 0:
            continue
        mudou = depois / antes
        esperado = k if razao < 1 else 1 / k        # desdobramento: preço cai, quantidade sobe
        # a quantidade precisa ter mudado mais perto do fator esperado do que de "nada mudou"
        if abs(np.log(mudou / esperado)) < 0.5 * abs(np.log(esperado)):
            fator = (1 / k) if razao > 1 else k
            r.iloc[i] = razao * fator
    return r - 1


def yahoo(codigos: list[str]) -> dict[str, pd.Series]:
    import yfinance as yf
    arq = PASTA / "yahoo_close.parquet"
    tem = pd.read_parquet(arq) if arq.exists() else pd.DataFrame()
    faltam = [c for c in codigos if c not in tem.columns]
    novos = {}
    for k in range(0, len(faltam), 40):
        lote = [c + ".SA" for c in faltam[k:k + 40]]
        d = yf.download(lote, start="2002-01-01", progress=False, auto_adjust=True, threads=True)
        if d is None or not len(d):
            continue
        close = d["Close"] if isinstance(d.columns, pd.MultiIndex) else d[["Close"]].rename(columns={"Close": lote[0]})
        for c in close.columns:
            s = close[c].dropna()
            novos[c.replace(".SA", "")] = s if len(s) else pd.Series(dtype=float)
    for c in faltam:
        novos.setdefault(c, pd.Series(dtype=float))
    if novos:
        tem = pd.concat([tem, pd.DataFrame(novos)], axis=1)
        tem.index = pd.to_datetime(tem.index)
        tem.to_parquet(arq)
    return {c: tem[c].dropna() for c in codigos if c in tem.columns}


def montar(ini: int = 2003, fim: int = 2026):
    PASTA.mkdir(parents=True, exist_ok=True)
    cot = dados_b3.carregar(ini, fim)
    cods = candidatos(cot)
    print(f"{cot.codigo.nunique()} códigos na B3; {len(cods)} já estiveram entre os 200 mais negociados")
    cot = cot[cot.codigo.isin(cods)]
    yh = yahoo(cods)
    print(f"Yahoo tem {sum(1 for c in cods if len(yh.get(c, [])) > 0)} desses códigos")

    rets, vols, fontes = {}, {}, {}
    for cod, g in cot.groupby("codigo"):
        g = g.sort_values("data")
        bruto = retorno_bruto_corrigido(g)
        datas = bruto.index
        ry = pd.Series(np.nan, index=datas)
        if cod in yh and len(yh[cod]):
            y = yh[cod].reindex(datas)               # só nos dias em que o código negociou na B3
            ry = y / y.shift(1) - 1
        usa_y = ry.notna() & ((ry - bruto).abs() < 0.12)   # Yahoo coerente com o preço oficial
        r = bruto.where(~usa_y, ry)
        r.iloc[0] = np.nan
        rets[cod] = r
        vols[cod] = g.set_index("data")["volume"]
        fontes[cod] = usa_y.mean()
    ret = pd.DataFrame(rets).sort_index()
    vol = pd.DataFrame(vols).reindex(ret.index)
    ret.to_parquet(PASTA / "retorno.parquet")
    vol.to_parquet(PASTA / "volume.parquet")
    pd.Series(fontes, name="proporcao_yahoo").to_frame().to_parquet(PASTA / "fonte.parquet")
    print(f"Painel: {ret.shape[0]} pregões × {ret.shape[1]} códigos | "
          f"retornos vindos do Yahoo: {np.mean(list(fontes.values())):.0%} (média por código)")
    return ret, vol


def carregar():
    return pd.read_parquet(PASTA / "retorno.parquet"), pd.read_parquet(PASTA / "volume.parquet")


if __name__ == "__main__":
    montar()
