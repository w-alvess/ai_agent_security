CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". A etapa 2 deixou refined.incidentes tipado, com mes ('AAAA-MM')
e natureza preservados, e trouxe refined.tendencia_mensal como veio da
fonte. Este mart monta a série mensal e decide o que ela mostra; a decisão
fica escrita aqui. Spec-driven: a spec é a fonte da verdade. Não acrescente
requisito que não esteja escrito aqui. Se algo estiver ambíguo, pergunte
antes de escrever código.

PERGUNTA QUE O MART RESPONDE
O problema está crescendo — e o crescimento é de incidentes, de pesquisa
ou de regulação?

STACK
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Arquivo .sql em sql/marts/ com um único SELECT; pipeline/marts.py o
  grava como tabela (specs/03_marts.md).

O QUE JÁ EXISTE (use, não reimplemente)
refined.incidentes        (incidente_id, data, data_fim, precisao_data, mes,
                           natureza, severidade, dano_real, ...)  395 linhas
refined.tendencia_mensal  (mes, total_incidentes, incidentes_criticos,
                           incidentes_alta, incidentes_media,
                           dano_real_confirmado)                   23 linhas
mart.tipos_ataque         o primeiro mart, mesma forma

ARTEFATO A PRODUZIR
sql/marts/02_tendencia_mensal.sql: um único SELECT (pode começar com comentários
e WITH), gravado como tabela mart.tendencia_mensal por uv run python -m pipeline.marts.

SPEC

1. FORMA
   Um único SELECT, sem CREATE: pipeline.marts grava o resultado como
   tabela mart.tendencia_mensal (specs/03_marts.md). Lê só de refined.
   Motivo: a regra de negócio mora inteira no .sql; quem cria, recria e
   apaga tabelas é o pipeline, numa transação só.
   refined.tendencia_mensal não é fonte deste mart, só conferência
   (critérios de aceite). Motivo: ela não separa natureza nem marca mês
   parcial; recalcular a partir dos incidentes é o que permite as duas
   coisas, e bater com ela prova que o recálculo está certo.

2. GRÃO
   Uma linha por mês, 'AAAA-MM'. Mês é a menor granularidade.
   Motivo: 53 incidentes têm o dia inventado (precisao_data 'month' no dia
   01, 'part' no dia 15), mas o mês deles é verdadeiro. Por semana ou por
   dia, esses incidentes cairiam em dias que não aconteceram.
   Incidente com intervalo (data_fim preenchida, 14 casos, até 62 dias)
   conta uma vez, no mês de início — a coluna mes de refined.incidentes.
   Motivo: contar em todo mês atravessado faria a soma passar de 395 e
   transformaria "quantos começaram" em "quantos estavam ativos", que é
   outra pergunta.

3. MESES SEM BURACO
   Os meses vêm de uma sequência contínua do primeiro ao último mes de
   refined.incidentes, e não só dos meses que têm incidente. Mês sem
   nenhum aparece com 0 em todas as contagens.
   Motivo: na série, um mês que some faz a linha do gráfico ligar os
   vizinhos e esconder a queda. Hoje não há buraco (23 meses, 2024-12 a
   2026-10); a regra existe para quando houver.

4. NATUREZA LADO A LADO
   total e uma coluna por natureza: qtd_incident, qtd_research,
   qtd_policy, qtd_vulnerability, qtd_report.
   Motivo: o mart não decide o que é "incidente"; quem desenha o gráfico
   escolhe a linha. As duas leituras divergem: 2025-10 tem 15 no total e 1
   incident.

5. COLUNAS DE CONFERÊNCIA
   qtd_criticos (severidade = 'critical'), qtd_alta ('high'), qtd_media
   ('medium'), qtd_dano_confirmado (dano_real = true), todas as naturezas.
   Motivo: são as colunas de refined.tendencia_mensal, recalculadas; batem
   mês a mês com a fonte, ou o recálculo está errado.
   Contagens, não percentuais, pelo mesmo motivo do mart.tipos_ataque.

6. MÊS PARCIAL
   mes_parcial (BOOLEAN): true no mês da maior data de refined.incidentes,
   se essa data não for o último dia do mês; false em todos os outros.
   Hoje: só 2026-10 (maior data 2026-10-09).
   O mês parcial fica na série, com as contagens que tem.
   Motivo: apagar esconde 11 incidentes; deixar sem marca faz parecer que
   o problema despencou. A maior data é uma aproximação do fim da coleta,
   que o dataset não informa.

7. O QUE NÃO SE FAZ AQUI
   Nenhuma correção do pico de 2026-09 (80, contra 20-30 nos vizinhos,
   presente em todas as naturezas e com dia exato em 78 dos 80): é fato do
   dado. Nenhuma média móvel, nenhuma taxa de crescimento: é cálculo de
   gráfico, e cada um escolhe janela e base diferentes.

8. COLUNAS, nesta ordem
   mes, mes_parcial, total, qtd_incident, qtd_research, qtd_policy,
   qtd_vulnerability, qtd_report, qtd_criticos, qtd_alta, qtd_media,
   qtd_dano_confirmado.
   mes VARCHAR, contagens INTEGER. Ordenada por mes.

9. COMENTÁRIOS NO .sql
   Cabeçalho com a pergunta que o mart responde e o porquê de cada regra.
   Comentários no meio só onde a decisão não é óbvia.

CRITÉRIOS DE ACEITE
- 23 linhas, de 2024-12 a 2026-10, sem mês faltando.
- sum(total) = 395. Somas por natureza: incident 162, research 91,
  policy 72, vulnerability 55, report 15; e as cinco somam total em todas
  as linhas.
- total, qtd_criticos, qtd_alta, qtd_media e qtd_dano_confirmado batem
  com total_incidentes, incidentes_criticos, incidentes_alta,
  incidentes_media e dano_real_confirmado de refined.tendencia_mensal nos
  23 meses.
- mes_parcial true só em 2026-10.
- 2026-09: total 80, incident 32, policy 17, research 13,
  vulnerability 13, report 5.
- 2025-10: total 15, incident 1.
- Rodar uv run python -m pipeline.marts duas vezes seguidas não muda o
  resultado.

ENTREGA, nesta ordem
1. A spec resumida como comentário no topo do .sql, dizendo por que cada
   regra existe.
2. O SQL.
3. Uma lista final do que você assumiu e que não estava na spec.
