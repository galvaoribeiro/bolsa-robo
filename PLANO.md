# Plano para começar a operar na bolsa (v2)

> **Pendência:** o arquivo `reddit_comentarios_2_threads.md` não estava mais disponível quando retomei
> (o ambiente na nuvem foi reiniciado). Se quiser que eu incorpore os comentários, envie de novo.
> Este plano já está ajustado às suas 4 respostas.

## Seu perfil e o que ele define
| Resposta | Consequência |
|---|---|
| ~30 min/dia, fora do expediente | **Nada de day trade.** Decisões só com o fechamento do dia, à noite. Ordens deixadas na corretora para o pregão seguinte. |
| Programa | O sistema roda em Python. Eu escrevo e reviso o código com você. |
| Sem corretora | Primeiro testar com dados gratuitos; abrir conta só na Etapa 2. |
| Mercado em aberto | **Ações e ETFs da B3, swing trade no gráfico diário.** |

**Por que não day trade:** você não acompanharia o pregão, o IR é maior (20% contra 15%) e a
estatística da CVM/FGV (97% dos day traders perdem dinheiro) vale para quem opera em tempo integral.

## Etapas (só se avança passando no critério)

### Etapa 1 — Backtest (semanas 1 a 4) · sem corretora, sem dinheiro
- `pip install yfinance pandas` e rodar `python backtest_mm200.py` (o arquivo já está pronto nesta pasta).
- O script baixa a BOVA11 desde 2010 e compara a regra da MM200 com comprar e segurar.
  Ele inclui custos e testa as duas metades do período separadamente.
- Depois testamos 2 ou 3 variações simples (outras janelas, uma cesta de ETFs, momentum).
  **Limite de 3 a 5 ideias testadas.** Testar dezenas até uma "funcionar" é otimização excessiva (overfitting).
- **Critério para avançar:** a regra precisa ser melhor que comprar e segurar, ou ter queda máxima bem menor,
  **nas duas metades**. Se não passar, isso também é resultado: a alternativa é investir em ETF/Tesouro e encerrar o projeto.

### Etapa 2 — Conta + simulado (meses 2 a 4)
- **Corretora:** escolha uma que dê acesso ao **MetaTrader 5 para B3** com **conta demo**.
  Clear, XP, Rico, Genial e Modal costumam oferecer, mas as condições mudam: confirme no site de cada uma
  se o MT5 é gratuito, se a demo usa dados reais e se aceita **ordens com validade até cancelar**.
- Observação técnica: a biblioteca `MetaTrader5` do Python **só funciona no Windows**.
- O script roda todo dia às 19h (Agendador de Tarefas), lê os dados pelo MT5, calcula o sinal e envia a ordem para a conta demo.
- Seus 30 min/dia: ler o log, conferir se a ordem executada bate com o sinal e anotar divergências.
- **Critério:** 2 a 3 meses sem erro operacional, e resultado da demo coerente com o backtest.

### Etapa 3 — Dinheiro real pequeno (meses 5 a 10)
- Comece com um valor cuja perda total você aceitaria (ex.: R$ 1–3 mil). Mesmo código, conta real.
- Travas no código: tamanho máximo de posição, perda máxima mensal que desliga o robô e alerta se a ordem não for executada.
- Stop sempre registrado na corretora, nunca só no seu PC.

### Etapa 4 — Escalar
- Só depois de 6 meses ou mais de operação real coerente com o teste. Aumente o capital aos poucos.

## Impostos (swing trade em ações)
- 15% sobre o lucro, pago por **DARF até o último dia útil do mês seguinte**.
- Ações: isenção quando o total de **vendas** no mês fica abaixo de R$ 20 mil. **ETFs não têm essa isenção.**
- Prejuízo pode ser compensado com lucros futuros. Guarde as notas de corretagem; o script pode gerar a planilha.

## O papel do Claude
Escrever e revisar o código, achar erros no backtest (olhar o futuro, ignorar custos) e analisar os logs com você.
**Não** escolher ações nem dizer "compre agora". A regra é definida e testada antes; o robô só executa.

## Próximas ações
1. [ ] Instalar Git e VS Code; rodar `backtest_mm200.py` no seu computador e me mandar a saída.
2. [ ] (Opcional) Reenviar `reddit_comentarios_2_threads.md`.
3. [ ] Confirmar se seu computador é Windows (por causa do MT5).

## Diário de resultados
- **2026-11-24 — MM200 na BOVA11** (`resultados/2026-11-24_mm200_bova11.txt`): reduz a queda máxima
  (−31% contra −50%), mas rende menos que comprar e segurar e menos que o CDI. Não serve como robô.
- **2026-11-24 — Swing trade, 15 ações** (`resultados/2026-11-24_swing_correcao_vs_reddit.txt`):
  - A) Correção com stop: fator de lucro 1,01 (zero vantagem depois dos custos); perde para o CDI na 2ª metade. **Reprovada.**
  - B) Estratégia do Reddit (preço médio para baixo, sem stop): 100% de acerto nas 15 ações que sobreviveram,
    mas zerou a conta na Americanas e teve quedas de −74% a −81% em Oi, Casas Bahia, CVC e Magalu. **Reprovada por risco.**
- **2026-11-24 — Momentum mensal** (`resultados/2026-11-24_momentum_mensal.txt`):
  - Nas 15 sobreviventes, o momentum (+13,6% ao ano) rende menos que só comprar e segurar as mesmas ações (+14,8%).
  - Com as 21 ações (incluindo as que quebraram): +14,8% ao ano contra +10,0% do CDI, mas quase todo o ganho
    veio da 1ª metade (+20,2%). Na 2ª metade (2019–2026) empatou com o CDI (+9,7% contra +9,6%), com queda de −50% na pandemia.
  - Pequenas mudanças na regra alteram muito o resultado (de +5% a +17% ao ano). Sinal de fragilidade.
  - **Não passa no critério** (bater o CDI com folga nas duas metades).
- **2026-11-24 — Setup 9.1 (Larry Williams), diário, só compra** (`resultados/2026-11-24_setup91.txt`):
  - 15 sobreviventes: +5,6% ao ano contra +10,0% do CDI. BOVA11: +5,3%. Acerta 26–27% das operações; fator de lucro 1,03–1,07.
  - Nas 21 ações deu +14,8%, mas só por causa da Magalu (subiu mais de 100x em 2015–2020). Sem ela: +4,6%.
  - Pior operação: −71,5% (Americanas, jan/2023). A ação abriu muito abaixo do stop, então o stop não protegeu.
  - **Reprovado.** É a 5ª ideia testada: o limite do plano foi atingido.
