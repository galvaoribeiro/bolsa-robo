"""
Família 7 do PROTOCOLO.md: metade em multiativos com tendência + metade na melhor carteira de ações.

Multiativos: regra padrão da literatura (Faber), sem escolher pelo resultado: média de 10 meses,
pesos iguais, Ibovespa, S&P 500 em reais, ouro em reais e Treasuries em reais.
Ações: a configuração de ações com maior Sharpe nas famílias 1–4 (passada como argumento).

Uso: python estrategias_combinadas.py
"""
import json
import sys

import pandas as pd

import dados
import estrategias_acoes as ea
import estrategias_multiativos as em
import motor


def combinar(dec_a, dec_b, peso_a=0.5):
    def decidir(d):
        a, b = dec_a(d), dec_b(d)
        return pd.concat([a * peso_a, b * (1 - peso_a)]).groupby(level=0).sum()
    return decidir


def precos_juntos(s: ea.Sinais, m: pd.DataFrame) -> pd.DataFrame:
    idx = s.preco.index.union(m.index)
    return pd.concat([s.preco.reindex(idx), m.reindex(idx)], axis=1)


def main(params_acoes: dict, dividendos="media"):
    cdi = dados.cdi()
    s = ea.Sinais(dividendos=dividendos)
    m, _, cdi_idx, mensal = em.preparar()
    precos = precos_juntos(s, m)
    multi = em.tendencia(m, cdi_idx, mensal, ["IBOV", "SPX", "OURO", "TREA"], 10, "iguais")
    acoes = ea.estrategia(s, **params_acoes)
    for peso in [0.5]:
        nome = f"F7 {int(peso*100)}% multiativos 10m + {int((1-peso)*100)}% ações {params_acoes}"
        r = motor.simular(precos, combinar(multi, acoes, peso), cdi, inicio="2005-01-01", custo=0.0015)
        met = motor.metricas(r.curva, cdi)
        motor.registrar("7_combinada", nome, {"peso_multi": peso, "acoes": params_acoes, "dividendos": dividendos,
                                              "custo": 0.0015}, met, {"giro_anual": round(r.giro_anual, 2)})
        print(motor.linha_texto(nome[:42], met) + f" | giro {r.giro_anual:.1f}x")


if __name__ == "__main__":
    main(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"sinal": "mom12", "tamanho": "terco"})
