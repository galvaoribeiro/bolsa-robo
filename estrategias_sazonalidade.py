"""
Família 8 do PROTOCOLO.md: efeito virada do mês no Ibovespa (verificação rápida).

Regra: comprado no Ibovespa (BOVA11) do fechamento do penúltimo pregão do mês até o fechamento
do N-ésimo pregão do mês seguinte; no resto do tempo, CDI. Custo 0,10% por lado (2 operações/mês).

Uso: python estrategias_sazonalidade.py
"""
import pandas as pd

import dados
import motor


def main():
    cdi = dados.cdi()
    ibov = dados.multiativos()["IBOV"]
    r = ibov.pct_change().dropna()
    datas = r.index
    s = pd.Series(range(len(datas)), index=datas)
    mes = datas.to_period("M")
    pos_no_mes = s.groupby(mes).cumcount()                 # 0 = 1º pregão do mês
    do_fim = s.groupby(mes).cumcount(ascending=False)      # 0 = último pregão do mês
    rf = cdi.reindex(datas).fillna(0)
    print("Virada do mês no Ibovespa (resto do tempo no CDI), custo 0,10% por lado:")
    for n in [2, 3, 4]:
        # retorno do dia t pertence à janela se t é o último pregão do mês ou um dos n primeiros
        janela = (do_fim == 0) | (pos_no_mes < n)
        entra = janela & ~janela.shift(1, fill_value=False)
        sai = ~janela & janela.shift(1, fill_value=False)
        ret = r.where(janela, rf) - 0.001 * (entra.astype(int) + sai.astype(int))
        curva = (1 + ret["2005":]).cumprod()
        m = motor.metricas(curva, cdi)
        motor.registrar("8_sazonalidade", f"Virada do mês -1/+{n}", {"n": n, "custo": 0.001}, m)
        print(motor.linha_texto(f"Virada do mês -1/+{n}", m) + f" | tempo comprado {janela.mean():.0%}")


if __name__ == "__main__":
    main()
