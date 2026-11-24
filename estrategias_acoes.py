"""
Famílias 1–4 do PROTOCOLO.md: carteiras de ações da B3, painel sem viés de sobrevivência.

Universo de cada fim de mês (só dados até aquele dia):
  - média de volume financeiro diário dos últimos 63 pregões, entre as N maiores (padrão 100)
  - negociou em >= 90% dos últimos 63 pregões e tem >= 252 pregões de histórico
  - uma classe por empresa (a mais negociada entre ON/PN/UNT)
Sinais:
  - momentum: retorno total dos últimos 12 meses sem o último (12-1); variante 6-1
  - volatilidade: desvio-padrão dos retornos diários dos últimos 252 pregões
Carteiras (peso igual, mensal, só compra):
  F1 momentum: terço superior (ou top 20 / top 10)
  F2 F1 + filtro: Ibovespa abaixo da média de N meses -> 100% CDI
  F3 F1 + meta de volatilidade: exposição = min(1, meta / vol estimada da carteira), resto no CDI
  F4 baixa volatilidade (terço inferior) e combinação momentum + baixa vol (média dos rankings)

Uso: python estrategias_acoes.py
"""
import numpy as np
import pandas as pd

import dados
import motor
import painel_acoes

CUSTO = 0.002


class Sinais:
    def __init__(self, n_universo=100, dividendos="media"):
        ret, vol = painel_acoes.carregar(dividendos)
        self.dividendos = dividendos
        self.ret = ret
        datas = ret.index
        negociou = ret.notna() | vol.notna()
        # índice de retorno total; NaN nos dias em que o código não negociou
        self.preco = (1 + ret.fillna(0)).cumprod().where(negociou)
        self.liq = vol.fillna(0).rolling(63, min_periods=63).mean()
        self.frac = negociou.rolling(63, min_periods=63).mean()
        self.hist = negociou.cumsum()
        r0 = ret.fillna(0)
        logr = np.log1p(r0)
        cum = logr.cumsum()
        self.mom12 = np.exp(cum.shift(21) - cum.shift(252)) - 1
        self.mom6 = np.exp(cum.shift(21) - cum.shift(126)) - 1
        self.vol = ret.rolling(252, min_periods=200).std() * np.sqrt(252)
        self.n_universo = n_universo
        ibov = dados.precos(["^BVSP"])["^BVSP"]["Close"]
        self.ibov_m = ibov.groupby([ibov.index.year, ibov.index.month]).tail(1)

    def universo(self, d, n=None):
        n = n or self.n_universo
        liq, frac, hist = self.liq.loc[d], self.frac.loc[d], self.hist.loc[d]
        ok = (frac >= 0.9) & (hist >= 252) & liq.notna() & (liq > 0)
        cand = liq[ok].sort_values(ascending=False)
        empresas, escolhidos = set(), []
        for cod in cand.index:                          # uma classe por empresa
            emp = cod[:4]
            if emp in empresas:
                continue
            empresas.add(emp)
            escolhidos.append(cod)
            if len(escolhidos) >= n:
                break
        return escolhidos

    def ibov_acima_media(self, d, meses):
        h = self.ibov_m[self.ibov_m.index <= d]
        return h.iloc[-1] > h.iloc[-meses:].mean() if len(h) >= meses else True

    def vol_carteira(self, d, codigos):
        r = self.ret.loc[:d, codigos].iloc[-63:].fillna(0)
        return r.mean(axis=1).std() * np.sqrt(252)


def selecionar(s: Sinais, d, sinal: str, tamanho):
    u = s.universo(d)
    if len(u) < 30:
        return []
    if sinal == "mom12":
        score = s.mom12.loc[d, u]
    elif sinal == "mom6":
        score = s.mom6.loc[d, u]
    elif sinal == "baixavol":
        score = -s.vol.loc[d, u]
    elif sinal == "mom_baixavol":
        score = s.mom12.loc[d, u].rank() + (-s.vol.loc[d, u]).rank()
    else:
        raise ValueError(sinal)
    score = score.dropna()
    n = int(round(len(score) / 3)) if tamanho == "terco" else int(tamanho)
    return list(score.sort_values(ascending=False).head(n).index)


def estrategia(s: Sinais, sinal="mom12", tamanho="terco", filtro_meses=None, meta_vol=None):
    def decidir(d):
        if filtro_meses and not s.ibov_acima_media(d, filtro_meses):
            return pd.Series(dtype=float)
        esc = selecionar(s, d, sinal, tamanho)
        if not esc:
            return pd.Series(dtype=float)
        expo = 1.0
        if meta_vol:
            v = s.vol_carteira(d, esc)
            expo = min(1.0, meta_vol / v) if v > 0 else 1.0
        return pd.Series(expo / len(esc), index=esc)
    return decidir


def rodar(s, cdi, nome, familia, params, custo=CUSTO, ir=False, imprimir=True):
    r = motor.simular(s.preco, estrategia(s, **params), cdi, inicio="2005-01-01", custo=custo, ir=ir)
    m = motor.metricas(r.curva, cdi)
    motor.registrar(familia, nome, {**params, "custo": custo, "ir": ir, "dividendos": s.dividendos}, m,
                    {"giro_anual": round(r.giro_anual, 2)})
    if imprimir:
        print(motor.linha_texto(nome, m) + f" | giro {r.giro_anual:.1f}x")
    return r, m


def main():
    cdi = dados.cdi()
    s = Sinais()
    print("Custo 0,20% por lado | colunas: ao ano (CDI) | blocos 2005-09, 2010-14, 2015-19, 2020-26 | queda | sharpe | critérios\n")
    print("--- Referência: todas as ações do universo, peso igual ---")
    rodar(s, cdi, "Universo inteiro (100 mais líquidas)", "referencia", dict(sinal="mom12", tamanho=1000))

    print("\n--- Família 1: momentum ---")
    for sinal in ["mom12", "mom6"]:
        for tam in ["terco", 20, 10]:
            rodar(s, cdi, f"F1 {sinal} {tam}", "1_momentum", dict(sinal=sinal, tamanho=tam))

    print("\n--- Família 2: momentum + filtro de tendência do Ibovespa ---")
    for tam in ["terco", 20]:
        for fm in [6, 10, 12]:
            rodar(s, cdi, f"F2 mom12 {tam} filtro {fm}m", "2_mom_filtro", dict(sinal="mom12", tamanho=tam, filtro_meses=fm))

    print("\n--- Família 3: momentum + meta de volatilidade ---")
    for tam in ["terco", 20]:
        for mv in [0.12, 0.15, 0.20]:
            rodar(s, cdi, f"F3 mom12 {tam} metavol {mv:.0%}", "3_mom_metavol", dict(sinal="mom12", tamanho=tam, meta_vol=mv))
        rodar(s, cdi, f"F2+F3 mom12 {tam} filtro 10m metavol 15%", "3_mom_metavol",
              dict(sinal="mom12", tamanho=tam, filtro_meses=10, meta_vol=0.15))

    print("\n--- Família 4: baixa volatilidade e combinação ---")
    for sinal in ["baixavol", "mom_baixavol"]:
        for tam in ["terco", 20]:
            rodar(s, cdi, f"F4 {sinal} {tam}", "4_baixavol", dict(sinal=sinal, tamanho=tam))
        rodar(s, cdi, f"F4 {sinal} terco filtro 10m", "4_baixavol", dict(sinal=sinal, tamanho="terco", filtro_meses=10))


if __name__ == "__main__":
    main()
