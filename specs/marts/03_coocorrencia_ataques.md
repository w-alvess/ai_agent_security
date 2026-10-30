CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". mart.tipos_ataque conta cada tipo isolado; este mart olha os
incidentes com mais de um tipo e pergunta quais tipos andam juntos.
Spec-driven: a spec é a fonte da verdade. Não acrescente requisito que não
esteja escrito aqui. Se algo estiver ambíguo, pergunte antes de escrever
código.

PERGUNTA QUE O MART RESPONDE
Quais tipos de ataque aparecem juntos no mesmo incidente — e isso acontece
em incidentes de verdade ou só em pesquisa?

STACK
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Arquivo .sql em sql/marts/ com um único SELECT; pipeline/marts.py o
  grava como tabela (specs/03_marts.md).

O QUE JÁ EXISTE (use, não reimplemente)
refined.tipos_ataque      (codigo, nome, ...)                        12 linhas
refined.incidente_tipos   (incidente_id, posicao, codigo_ataque)     511 linhas
refined.incidentes        (incidente_id, natureza, ...)              395 linhas
mart.tipos_ataque         só conferência (qtd_envolvido)

ARTEFATO A PRODUZIR
sql/marts/03_coocorrencia_ataques.sql: um único SELECT (pode começar com comentários
e WITH), gravado como tabela mart.coocorrencia_ataques por uv run python -m pipeline.marts.

SPEC

1. FORMA
   Um único SELECT, sem CREATE: pipeline.marts grava o resultado como
   tabela mart.coocorrencia_ataques (specs/03_marts.md). Lê só de refined.
   Motivo: a regra de negócio mora inteira no .sql; quem cria, recria e
   apaga tabelas é o pipeline, numa transação só.
   Não lê de outro mart. Motivo: a ordem dos arquivos fica irrelevante.

2. PAR SEM ORDEM
   Um par é {A, B} com A < B em ordem alfabética de código: IPI;EXFIL e
   EXFIL;IPI são o mesmo par (EXFIL, IPI).
   Motivo: a ordem em codigos_ataque não é documentada como prioridade
   (a mesma suposição que mart.tipos_ataque declarou em
   qtd_tipo_principal). Par ordenado afirmaria "IPI leva a EXFIL", e o
   dado não diz isso.

3. GRÃO
   Uma linha por par possível entre os 12 tipos de refined.tipos_ataque:
   66 linhas, inclusive as de contagem 0.
   Motivo: num mapa de calor, par ausente é casa vazia, não casa que
   some; "nunca aparecem juntos" é informação. OTHER, por exemplo, nunca
   se combina com nada (11 pares com 0).
   Incidente com 3 tipos gera 3 pares (A-B, A-C, B-C).
   Motivo: cada par realmente coocorreu ali; contar só um exigiria
   escolher qual, e não há critério. Por isso a soma de qtd_juntos (119)
   passa do número de incidentes com mais de um tipo (113).

4. COLUNAS
   codigo_a, nome_a, codigo_b, nome_b
   qtd_juntos                  incidentes com A e B, todas as naturezas
   qtd_juntos_so_incidentes    o mesmo, só natureza = 'incident'
   qtd_envolvido_a             incidentes com A em qualquer posição
   qtd_envolvido_b             idem para B
   Contagens INTEGER, nomes VARCHAR. Ordenada por qtd_juntos decrescente,
   desempate por codigo_a e codigo_b.
   Motivo de qtd_juntos_so_incidentes: EXFIL+IPI é o par mais frequente
   (24), mas só 3 são incidentes; CRED+SUPPLY tem 19, e 18 são. Sem a
   coluna, o par que lidera é o de pesquisa.
   Motivo de qtd_envolvido_a/b: 24 juntos significa uma coisa se A aparece
   35 vezes e outra se aparece 500. Ficam as bases, não o percentual —
   qual das duas é o denominador é decisão de quem lê.

5. COMENTÁRIOS NO .sql
   Cabeçalho com a pergunta que o mart responde e o porquê de cada regra.
   Comentários no meio só onde a decisão não é óbvia.

CRITÉRIOS DE ACEITE
- 66 linhas; codigo_a < codigo_b em todas.
- sum(qtd_juntos) = 119; 32 linhas com qtd_juntos > 0.
- EXFIL/IPI: 24 juntos, 3 só incidentes. CRED/SUPPLY: 19 e 18.
- Os 11 pares com OTHER têm qtd_juntos = 0.
- qtd_juntos <= menor entre qtd_envolvido_a e qtd_envolvido_b, e
  qtd_juntos_so_incidentes <= qtd_juntos, em todas as linhas.
- qtd_envolvido_a e qtd_envolvido_b batem com mart.tipos_ataque.qtd_envolvido.
- Rodar uv run python -m pipeline.marts duas vezes seguidas não muda o
  resultado.

ENTREGA, nesta ordem
1. A spec resumida como comentário no topo do .sql, dizendo por que cada
   regra existe.
2. O SQL.
3. Uma lista final do que você assumiu e que não estava na spec.
