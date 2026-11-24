"""
Validação de finalistas pelos critérios 4–6 do PROTOCOLO.md.

validar(nome, construir, vizinhos, precos, cdi, custo_base, ativos_para_remover)
  construir(**params) -> função decidir(d)
  vizinhos: lista de dicts de parâmetros (o primeiro é a configuração finalista)
Mostra: finalista, vizinhos, custo dobrado, com IR, sem o ativo que mais contribuiu,
e o Sharpe deflacionado pelo número de tentativas registradas em resultados/tentativas.csv.
"""
import pandas as pd

import motor


def sharpe_deflacionado_da_base(m: dict) -> tuple[float, int]:
    t = pd.read_csv(motor.ARQ_TENTATIVAS)
    t = t[t["familia"] != "referencia"]
    n = len(t)
    var = float(t["sharpe"].var()) if n > 1 else 0.0
    p = motor.sharpe_deflacionado(m["sharpe"], m["n_dias"], n, var, m["assimetria"], m["curtose"])
    return p, n


def validar(nome, construir, vizinhos, precos, cdi, custo_base, remover=None, inicio="2005-01-01"):
    print(f"\n================ Validação: {nome} ================")
    base = vizinhos[0]
    r = motor.simular(precos, construir(**base), cdi, inicio=inicio, custo=custo_base)
    m = motor.metricas(r.curva, cdi)
    cdi_aa = m["cdi_ao_ano"]
    print(motor.linha_texto("FINALISTA " + str(base), m))
    ok = {}

    piores = []
    for p in vizinhos[1:]:
        rv = motor.simular(precos, construir(**p), cdi, inicio=inicio, custo=custo_base)
        mv = motor.metricas(rv.curva, cdi)
        piores.append(mv["ao_ano"])
        print(motor.linha_texto("  vizinho " + str(p), mv))
    ok["c5a_vizinhos_cdi+3"] = min(piores) >= cdi_aa + 0.03 if piores else True

    rc = motor.simular(precos, construir(**base), cdi, inicio=inicio, custo=2 * custo_base)
    mc = motor.metricas(rc.curva, cdi)
    print(motor.linha_texto("  custo dobrado", mc))
    ok["c5b_custo2x_cdi+3"] = mc["ao_ano"] >= cdi_aa + 0.03

    ri = motor.simular(precos, construir(**base), cdi, inicio=inicio, custo=custo_base, ir=True)
    mi = motor.metricas(ri.curva, cdi)
    print(motor.linha_texto("  com IR de 15% (informativo)", mi))

    if remover:
        piores_rem = []
        for a in remover:
            sem = precos.drop(columns=[a])
            rr = motor.simular(sem, _sem_ativo(construir(**base), a), cdi, inicio=inicio, custo=custo_base)
            mr = motor.metricas(rr.curva, cdi)
            piores_rem.append(mr["ao_ano"])
            print(motor.linha_texto(f"  sem {a}", mr))
        ok["c6_sem_melhor_cdi+3"] = min(piores_rem) >= cdi_aa + 0.03

    p, n = sharpe_deflacionado_da_base(m)
    print(f"  Sharpe deflacionado: probabilidade de Sharpe real > 0 = {p:.0%} (considerando {n} tentativas)")
    ok["c4b_dsr_90"] = p >= 0.90
    basicos = motor.criterios_basicos(m)
    todos = {**basicos, **ok}
    print("  Critérios:", " | ".join(f"{k}: {'ok' if v else 'FALHA'}" for k, v in todos.items()))
    print("  RESULTADO:", "PASSA EM TUDO" if all(todos.values()) else "NÃO PASSA")
    return all(todos.values()), m, mi


def _sem_ativo(decidir, ativo):
    def novo(d):
        w = decidir(d)
        return w.drop(labels=[ativo], errors="ignore")
    return novo
