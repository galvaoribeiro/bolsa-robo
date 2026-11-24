# Protocolo da busca por uma estratégia de swing trade "ótima"

Escrito **antes** dos testes, em 2026-11-24. Não muda depois de ver resultados.
Se algo mudar, a mudança é registrada aqui com data e motivo.

## Por que um protocolo
Testando muitas estratégias, alguma vai parecer ótima só por sorte. Para reduzir isso:
1. As regras vêm da literatura, com os parâmetros padrão. Não são ajustadas para o histórico.
2. **Toda** configuração testada é registrada em `resultados/tentativas.csv`, inclusive as ruins.
3. A vencedora é avaliada com o **Sharpe deflacionado** (Bailey & López de Prado), que desconta o número de tentativas.
4. Cada vencedora passa por testes de robustez: parâmetros vizinhos, custos dobrados, IR e retirada do melhor ativo.

## Contaminação já existente (transparência)
- Os testes anteriores (MM200, IFR2, Reddit, momentum com 21 ações, 9.1) usaram 2010–2026 inteiro.
- Na pesquisa, vi o resultado de 2001–2026 das carteiras de estilo do NEFIN, inclusive de 2020–2026.
  Por isso **não existe mais um período totalmente "virgem"**. A proteção possível passa a ser:
  regras padrão da literatura, poucas variações, avaliação em 4 blocos de tempo e, no fim,
  **simulação em tempo real (conta demo) por 3 meses antes de colocar dinheiro**.

## Dados
- Ações: histórico oficial da B3 (COTAHIST, todas as ações, inclusive as que saíram da bolsa),
  combinado com preços ajustados do Yahoo quando o mesmo código está lá.
  Nos trechos sem Yahoo não há proventos (viés conservador).
- Universo de cada mês: as ~100 ações mais negociadas nos 3 meses anteriores, com negócios em ≥ 90% dos pregões.
  Decisão só com dados até o dia da decisão.
- Multiativos em reais: Ibovespa, S&P 500 (SPY ajustado × dólar), ouro (GLD × dólar), dólar, CDI (BC).
- Referência sem viés de sobrevivência: carteiras de estilo do NEFIN (USP).

## Regras de teste
- Período: jan/2005 a nov/2026. Blocos: 2005–09, 2010–14, 2015–19, 2020–26.
- Decisão no fechamento do último pregão do mês; execução na abertura do pregão seguinte.
- Custos por lado: ações 0,20% (teste de estresse 0,40%); ETFs/índices 0,10%.
- Caixa rende CDI. Só posições compradas, sem alavancagem.
- IR: 15% sobre ganho realizado, com compensação de prejuízo (para as finalistas).

## Critério para "realmente ótima" (todos obrigatórios)
1. Retorno anual ≥ **CDI + 5 pontos** no período inteiro, depois dos custos.
2. Acima do CDI em pelo menos 3 dos 4 blocos, **incluindo 2020–26**.
3. Pior queda (do pico ao fundo) **≤ 30%**.
4. Sharpe sobre o CDI ≥ 0,5, e Sharpe deflacionado com probabilidade ≥ 90%.
5. Robusta: parâmetros vizinhos (±50%) mantêm retorno ≥ CDI + 3 pontos; com custos dobrados, continua ≥ CDI + 3.
6. Não depende de um único ativo: tirar o que mais contribuiu mantém retorno ≥ CDI + 3.
7. Cabe na rotina: no máximo uma decisão por semana, executável à noite.

## Famílias a testar (lista fechada)
1. Momentum amplo (12 meses sem o último, terço superior, peso igual, mensal)
2. Momentum + filtro de tendência do mercado (Ibovespa acima da média de 10 meses, senão CDI)
3. Momentum com controle de volatilidade (meta de volatilidade, reduz a exposição quando o risco sobe)
4. Baixa volatilidade, e combinação momentum + baixa volatilidade
5. Multiativos: dual momentum (Ibovespa, S&P 500 em reais, ouro em reais ou CDI)
6. Multiativos: tendência por ativo com peso pelo risco (cada ativo entra se acima da média de 10 meses)
7. Combinação de 6 (multiativos) com a melhor carteira de ações
8. Sazonalidade de virada de mês no Ibovespa (verificação rápida)

## Alterações registradas
- **2026-11-24 — Proventos nos trechos sem Yahoo.** Na montagem do painel, ~70% dos códigos que já estiveram
  entre os 200 mais negociados não existem no Yahoo (troca de código, incorporação, saída da bolsa) e só têm preço
  bruto da B3, sem dividendos. Uma rodada de depuração (2005–2016, não registrada como tentativa) deu momentum
  6,6 pontos abaixo da carteira equivalente do NEFIN. Isso se explica por custos (~2,3 pontos) e falta de proventos.
  Decisão: rodar as famílias de ações com o **dividend yield médio do mercado (NEFIN)** somado nesses trechos
  (estimativa central) e repetir as finalistas **sem proventos** nesses trechos (limite pessimista).
  Nenhuma regra de estratégia ou critério mudou.
- **2026-11-24 — Limpeza do preço bruto.** Grupamentos de até 250.000:1 (2004–2008) e "prints" isolados antes de
  mudanças de instrumento geravam retornos falsos de até +250.000% num dia. Saltos são tratados como evento
  societário quando a quantidade negociada muda na proporção inversa; saltos acima de 50% depois de pregão com
  menos de 10 negócios ou pausa de mais de 5 pregões, ou acima de +300% sem confirmação, ficam sem retorno.
