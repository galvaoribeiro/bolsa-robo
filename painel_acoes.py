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
FATORES = np.array([1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100, 200, 250, 500, 1000,
                    2000, 2500, 5000, 10000, 20000, 25000, 50000, 100000, 250000], float)


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
    """Retorno diário pelo preço oficial, desfazendo desdobramentos/grupamentos detectados.
    Um salto de preço é tratado como evento societário quando a quantidade negociada muda na
    proporção inversa (mais perto do fator do salto do que de "nada mudou"). Fatores grandes
    (ex.: grupamento de 10.000 para 1, comum em 2004–2008) também são cobertos."""
    df = df.set_index("data").sort_index()
    p, q = df["fechamento"], df["quantidade"].astype(float)
    r = p / p.shift(1)
    for i in np.where((r > 1.45) | (r < 0.70))[0]:
        razao = r.iloc[i]
        antes = q.iloc[max(0, i - 20):i].median()
        depois = q.iloc[i:i + 20].median()
        if not (antes > 0 and depois > 0):
            continue
        esperado = 1 / razao                         # desdobramento: preço cai, quantidade sobe
        mudou = depois / antes
        if abs(np.log(mudou / esperado)) < 0.5 * abs(np.log(esperado)):
            alvo = razao if razao > 1 else 1 / razao
            k = FATORES[np.argmin(np.abs(FATORES / alvo - 1))]
            fator = k if abs(k / alvo - 1) <= 0.12 else alvo   # fator "redondo" quando bate
            r.iloc[i] = razao / fator if razao > 1 else razao * fator
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

    calendario = pd.Index(sorted(cot["data"].unique()))
    rets, vols, fontes, mascaras = {}, {}, {}, {}
    descartados = 0
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
        # saltos depois de negociação rala/pausa = reinício da série (mudança de instrumento,
        # print isolado); saltos > +300% sem confirmação = erro de dado. Ficam sem retorno.
        pos = calendario.get_indexer(g["data"])
        pausa = pd.Series(np.diff(pos, prepend=pos[0] - 1), index=datas)
        neg_ant = g.set_index("data")["negocios"].shift(1)
        suspeito = (r.abs() > 0.5) & ((neg_ant < 10) | (pausa > 5)) | (r > 3.0)
        descartados += int(suspeito.sum())
        r[suspeito] = np.nan
        rets[cod] = r
        vols[cod] = g.set_index("data")["volume"]
        fontes[cod] = usa_y.mean()
        mascaras[cod] = usa_y
    ret = pd.DataFrame(rets).sort_index()
    vol = pd.DataFrame(vols).reindex(ret.index)
    ret.to_parquet(PASTA / "retorno.parquet")
    vol.to_parquet(PASTA / "volume.parquet")
    pd.Series(fontes, name="proporcao_yahoo").to_frame().to_parquet(PASTA / "fonte.parquet")
    pd.DataFrame(mascaras).reindex(ret.index).fillna(False).astype(bool).to_parquet(PASTA / "do_yahoo.parquet")
    print(f"Retornos descartados como reinício de série/erro: {descartados}")
    print(f"Painel: {ret.shape[0]} pregões × {ret.shape[1]} códigos | "
          f"retornos vindos do Yahoo: {np.mean(list(fontes.values())):.0%} (média por código)")
    return ret, vol


def carregar(dividendos: str = "media"):
    """dividendos='nenhum': trechos sem Yahoo ficam sem proventos (limite pessimista).
    dividendos='media': nesses trechos soma o dividend yield médio do mercado (NEFIN) do período."""
    ret = pd.read_parquet(PASTA / "retorno.parquet")
    vol = pd.read_parquet(PASTA / "volume.parquet")
    if dividendos == "media":
        do_y = pd.read_parquet(PASTA / "do_yahoo.parquet").reindex_like(ret).fillna(False).astype(bool)
        dy = pd.read_csv(Path(__file__).parent / "dados" / "nefin" / "dividend_yield.csv")
        dy.index = pd.to_datetime(dict(year=dy.ano, month=dy.mes, day=dy.dia))
        dy = dy["yield_week_pc"].reindex(ret.index, method="ffill").bfill()
        diario = (1 + dy) ** (1 / 252) - 1
        add = pd.DataFrame(np.outer(diario.to_numpy(), np.ones(ret.shape[1])), index=ret.index, columns=ret.columns)
        ret = ret + add.where(ret.notna() & ~do_y, 0.0)
    return ret, vol


if __name__ == "__main__":
    montar()
