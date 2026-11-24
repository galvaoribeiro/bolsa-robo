"""
Resumo de resultados/tentativas.csv: quantas configurações foram testadas por família,
a melhor de cada uma (por Sharpe) e quantas passam nos critérios 1–4 do PROTOCOLO.md.

Uso: python resumo_tentativas.py
"""
import pandas as pd

import motor


def main():
    t = pd.read_csv(motor.ARQ_TENTATIVAS)
    print(f"Total de configurações registradas: {len(t)} "
          f"(sem contar referências: {(t.familia != 'referencia').sum()})\n")
    for fam, g in t.groupby("familia"):
        melhor = g.sort_values("sharpe", ascending=False).iloc[0]
        print(f"{fam:16s} | {len(g):3d} testadas | passam 1–4: {int(g.passa_1a4.sum()):2d} | melhor: {melhor['nome'][:40]:40s} "
              f"| {melhor['ao_ano']:+.1%} (CDI {melhor['cdi_ao_ano']:+.1%}) | queda {melhor['pior_queda']:+.1%} "
              f"| sharpe {melhor['sharpe']:+.2f}")
    passam = t[t.passa_1a4.astype(str) == "True"]
    if len(passam):
        print("\nPassam nos critérios 1–4 (seguem para validação):")
        for _, r in passam.sort_values("sharpe", ascending=False).iterrows():
            print(f"   {r['familia']:16s} {r['nome']}")
    else:
        print("\nNenhuma configuração passa nos critérios 1–4.")


if __name__ == "__main__":
    main()
