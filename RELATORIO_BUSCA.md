# Busca por uma estratégia de swing trade bem acima do CDI

Data: 2026-11-24. As regras foram definidas **antes** dos testes em `PROTOCOLO.md` (o commit é anterior aos
resultados). Todas as tentativas estão em `resultados/tentativas.csv`; as saídas completas, em `resultados/2026-11-24_*.txt`.

## Resposta curta
**Não encontrei nenhuma estratégia "realmente ótima"**, pelo critério combinado antes: CDI + 5 pontos,
queda máxima de até 30%, Sharpe ≥ 0,5, robusta a mudanças de parâmetro e sem depender de um único ativo.
Foram 54 configurações em 8 famílias, mais 186 variações de limite superior com os dados do NEFIN, sem custos.
**Nenhuma passou.**

A melhor opção realista é a **alocação com tendência entre bolsa brasileira, bolsa americana em reais e ouro**,
com decisão mensal via ETFs. Rendeu 14,9% ao ano contra 10,6% do CDI desde 2005, com queda máxima de −15%. Mas os
parâmetros vizinhos rendem só CDI + 2,5 a 3,5, e o resultado depende quase todo da bolsa americana em reais.

## 1. Pesquisa (internet e repositórios)
- **Momentum** é o estilo com mais evidência no Brasil. Nas carteiras do NEFIN (USP), sem viés de sobrevivência,
  o terço de ações que mais subiu nos 12 meses anteriores rendeu 19,9% ao ano em 2001–2026, contra 12,1% do CDI.
  Mas teve quedas de −56% a −62%, e esses números não descontam custos.
- **Baixa volatilidade:** resultados mistos em trabalhos brasileiros (dependem de medir por beta ou por desvio-padrão).
- **Fórmula Mágica e valor:** os estudos se comparam com o Ibovespa, não com o CDI. Um estudo de 2007–2017 deu
  11,1% ao ano, mais ou menos o CDI do período.
- **Dual momentum e tendência entre ativos:** não achei estudos em reais; testei aqui.
- **Repositórios:** os códigos encontrados (backtest de fatores na B3) não trazem resultados verificáveis. Os dados
  oficiais da B3 (COTAHIST) e do NEFIN são a melhor base pública.

## 2. Dados
- **Ações:** histórico oficial da B3 de 2003 a nov/2026, com **1.237 códigos, inclusive os que saíram da bolsa**,
  combinado com o Yahoo para proventos. Grupamentos (até 250.000:1), desdobramentos e "prints" isolados foram corrigidos.
  Nos trechos sem Yahoo, foi somado o dividend yield médio do mercado (NEFIN).
- **Multiativos em reais:** Ibovespa (bate com BOVA11), S&P 500 × dólar PTAX (bate com IVVB11 menos 0,8 ponto ao ano),
  ouro × dólar, Treasuries × dólar. Taxas de administração dos ETFs descontadas.
- **CDI:** série oficial do Banco Central, desde 2000.

## 3. Resultados (2005 a nov/2026, depois dos custos; CDI = 10,6% ao ano)

| Família | Testadas | Melhor configuração | Ao ano | Pior queda | Sharpe |
|---|---|---|---|---|---|
| 1. Momentum em ações | 6 | 6 meses, 20 ações | 11,3% | −59% | 0,15 |
| 2. Momentum + filtro do Ibovespa | 6 | 12 meses, terço superior, filtro 6m | 12,8% | −33% | 0,21 |
| 3. Momentum + meta de volatilidade | 8 | filtro 10m + meta 15% | 10,4% | −27% | 0,05 |
| 4. Baixa volatilidade / combinação | 6 | momentum + baixa vol, 20 ações | 13,2% | −48% | 0,22 |
| 5. Dual momentum multiativos | 12 | 9 meses, 2 ativos | 15,6% | −18% | 0,39 |
| 6. Tendência multiativos | 12 | 6 meses | 14,9% | −15% a −16% | 0,41–0,42 |
| 7. Multiativos + ações | 1 | 50% / 50% | 13,7% | −26% | 0,31 |
| 8. Virada do mês no Ibovespa | 3 | −1/+2 pregões | 13,2% | −17% | 0,29 |

Referências: Ibovespa 8,7% ao ano (queda −60%); 100 ações mais líquidas, peso igual: 7,5% (queda −61%);
S&P 500 em reais: 13,7% (queda −49%); ouro em reais: 13,6% (queda −30%).

**Limite superior com o NEFIN** (`resultados/2026-11-24_triagem_nefin.txt`): 186 combinações de estilo (valor,
tamanho, liquidez, momentum, setores, 2×2), puras e com filtro de tendência, **sem nenhum custo**. Nenhuma passou.
A melhor tem Sharpe de 0,49 e queda de −35%. Por isso não montei uma base de balanços da CVM para testar valor e
qualidade: nem a versão sem custos desses estilos chega lá.

## 4. Validação dos dois mais próximos (`resultados/2026-11-24_validacao_candidatos.txt`)
| | Tendência 6m | Dual momentum 9m |
|---|---|---|
| Resultado | 14,9% ao ano, queda −15% | 15,6% ao ano, queda −18% |
| Parâmetros vizinhos (3–9 meses / 5–13 meses) | 13,2% a 14,0% | 13,3% a 14,1% |
| Custos dobrados | 14,6% | 15,3% |
| Com IR de 15% sobre ganhos | 13,4% | 14,0% |
| **Sem a bolsa americana** | **12,1%** | **11,4%** |
| Sharpe deflacionado (54 tentativas) | 73% | 70% |

**Armadilha:** sem o Ibovespa, o dual momentum "passaria" (16,6% ao ano, Sharpe 0,52). Mas essa variação foi vista
**depois** do resultado, e escolhê-la seria exatamente o erro que o protocolo existe para evitar. O retorno dessas
estratégias vem sobretudo da bolsa americana somada à alta do dólar (R$ 2,70 em 2005 → R$ 5,90 em 2026), um ciclo que
pode não se repetir.

## 5. Por que é tão difícil bater o CDI com folga no Brasil
- O CDI médio foi de 10,6% ao ano desde 2005, sem risco e sem queda.
- O Ibovespa rendeu 8,7% ao ano, com queda de −60%. As ações médias (peso igual) renderam 7,5%; em 2020–2026, −1,3% ao ano.
- Os estilos que funcionam (momentum) têm quedas de −55% a −60%. Os filtros que cortam essas quedas também cortam o retorno.

## 6. Recomendação
1. **Não usar dinheiro real em nenhuma estratégia de ações deste estudo.**
2. **Se quiser uma estratégia sistemática:** tendência multiativos com ETFs da B3 (BOVA11, IVVB11, GOLD11 + Tesouro
   Selic), uma decisão por mês. Expectativa honesta: **CDI + 2 a 4 pontos**, com quedas de 10% a 20%, e risco de ficar
   perto do CDI se o dólar e a bolsa americana pararem de subir. É boa, mas não é ótima.
3. **Antes de qualquer dinheiro:** 3 meses de simulação em tempo real, como previsto no `PLANO.md`.
