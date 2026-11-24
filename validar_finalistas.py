"""
Validação (informativa) dos dois candidatos mais próximos do critério — nenhum passou nos critérios 1–4.
Uso: python validar_finalistas.py
"""
import dados
import estrategias_multiativos as em
import validacao


def main():
    m, cdi, cdi_idx, mensal = em.preparar()
    ativos = ["IBOV", "SPX", "OURO"]
    tend = lambda meses, pesos="iguais": em.tendencia(m, cdi_idx, mensal, ativos, meses, pesos)
    validacao.validar("Tendência multiativos 6m (pesos iguais)", tend,
                      [dict(meses=6), dict(meses=3), dict(meses=4), dict(meses=8), dict(meses=9)],
                      m, cdi, 0.001, remover=ativos)
    dm = lambda meses, n_top=2: em.dual_momentum(m, cdi_idx, mensal, ativos, meses, n_top)
    validacao.validar("Dual momentum 9m top 2", dm,
                      [dict(meses=9), dict(meses=5), dict(meses=6), dict(meses=12), dict(meses=13)],
                      m, cdi, 0.001, remover=ativos)


if __name__ == "__main__":
    main()
