"""
Histórico oficial da B3 (COTAHIST): todas as ações negociadas, inclusive as que saíram da bolsa.

- baixar_cotahist(ano): baixa e converte o arquivo anual para parquet em dados/b3/.
- carregar(ini, fim): DataFrame longo com data, codigo, especie, abertura, maxima, minima,
  fechamento, volume (R$), negocios, isin. Só mercado à vista, lote padrão, ações (ON/PN/UNT).

Layout oficial: https://www.b3.com.br (SeriesHistoricas_Layout.pdf).
Preços NÃO ajustados por proventos ou desdobramentos.
"""
import io
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

PASTA = Path(__file__).parent / "dados" / "b3"
URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"

# (nome, início, fim) com posições 1-indexadas do layout
CAMPOS = [("data", 3, 10), ("codbdi", 11, 12), ("codigo", 13, 24), ("tpmerc", 25, 27),
          ("especie", 40, 49), ("abertura", 57, 69), ("maxima", 70, 82), ("minima", 83, 95),
          ("fechamento", 109, 121), ("negocios", 148, 152), ("quantidade", 153, 170),
          ("volume", 171, 188), ("fatcot", 211, 217), ("isin", 231, 242)]


def _converter(linhas):
    regs = []
    for ln in linhas:
        if not ln.startswith("01") or ln[24:27] != "010" or ln[10:12] != "02":
            continue
        esp = ln[39:49].strip()
        if not esp.startswith(("ON", "PN", "UNT")):
            continue
        regs.append({n: ln[a - 1:b].strip() for n, a, b in CAMPOS})
    df = pd.DataFrame(regs)
    df["data"] = pd.to_datetime(df["data"], format="%Y%m%d")
    for c in ["abertura", "maxima", "minima", "fechamento", "volume"]:
        df[c] = df[c].astype("int64") / 100.0
    for c in ["negocios", "quantidade", "fatcot"]:
        df[c] = df[c].astype("int64")
    # preço por ação (alguns papéis antigos eram cotados por lote de 1000)
    for c in ["abertura", "maxima", "minima", "fechamento"]:
        df[c] = df[c] / df["fatcot"]
    return df.drop(columns=["codbdi", "tpmerc", "fatcot"])


def baixar_cotahist(ano: int, atualizar: bool = False) -> Path:
    PASTA.mkdir(parents=True, exist_ok=True)
    arq = PASTA / f"cotahist_{ano}.parquet"
    if arq.exists() and not atualizar:
        return arq
    import time
    req = urllib.request.Request(URL.format(ano=ano), headers={"User-Agent": "curl/8.0"})
    for espera in [0, 15, 45, 120, 300]:          # o servidor da B3 recusa pedidos seguidos (403)
        time.sleep(espera)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            break
        except urllib.error.HTTPError as e:
            if e.code != 403 or espera == 300:
                raise
    with z.open(z.namelist()[0]) as f:
        linhas = io.TextIOWrapper(f, encoding="latin-1").read().splitlines()
    _converter(linhas).to_parquet(arq, index=False)
    return arq


def carregar(ini: int = 2003, fim: int = 2026) -> pd.DataFrame:
    partes = [pd.read_parquet(baixar_cotahist(a)) for a in range(ini, fim + 1)]
    return pd.concat(partes, ignore_index=True).sort_values(["codigo", "data"])


if __name__ == "__main__":
    import sys
    from datetime import date
    ini = int(sys.argv[1]) if len(sys.argv) > 1 else 2003
    for ano in range(ini, date.today().year + 1):
        p = baixar_cotahist(ano, atualizar=(ano == date.today().year))
        print(ano, len(pd.read_parquet(p)), "linhas")
