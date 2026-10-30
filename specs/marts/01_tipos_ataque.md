CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". A etapa 2 deixou o dado tipado e as listas separadas em pontes
(refined.incidente_tipos), mas não decidiu como contar. Este mart decide, e
a decisão fica escrita aqui. Spec-driven: a spec é a fonte da verdade. Não
acrescente requisito que não esteja escrito aqui. Se algo estiver ambíguo,
pergunte antes de escrever código.

PERGUNTA QUE O MART RESPONDE
Quais tipos de ataque mais aparecem — e quanto disso é incidente de
verdade, crítico, com dano confirmado?

STACK
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Arquivo .sql em sql/marts/ com um único SELECT; pipeline/marts.py o
  grava como tabela (specs/03_marts.md).

O QUE JÁ EXISTE (use, não reimplemente)
refined.tipos_ataque      (codigo, nome, qtd_incidentes, descricao)  12 linhas
refined.incidente_tipos   (incidente_id, posicao, codigo_ataque)     511 linhas
refined.incidentes        (incidente_id, natureza, severidade, dano_real,
                           codigos_ataque, ...)                       395 linhas

ARTEFATO A PRODUZIR
sql/marts/01_tipos_ataque.sql: um único SELECT (pode começar com comentários
e WITH), gravado como tabela mart.tipos_ataque por uv run python -m pipeline.marts.

SPEC

1. FORMA
   Um único SELECT, sem CREATE: pipeline.marts grava o resultado como
   tabela mart.tipos_ataque (specs/03_marts.md). Lê só de refined.
   Motivo: a regra de negócio mora inteira no .sql; quem cria, recria e
   apaga tabelas é o pipeline, numa transação só.

2. GRÃO
   Uma linha por tipo de ataque de refined.tipos_ataque: 12 linhas.
   Tipo sem nenhum incidente aparece com 0, não some (LEFT JOIN a partir de
   tipos_ataque).
   Motivo: um tipo que some do ranking parece tipo que não existe.

3. AS TRÊS REGRAS DE CONTAGEM (a decisão central deste mart)
   Um incidente pode ter até 3 tipos (codigos_ataque = 'IPI;CRED').
   As três contagens ficam lado a lado, cada uma com o nome da regra:
     qtd_tipo_unico      incidentes cujo codigos_ataque é só este código.
                         É a regra do qtd_incidentes original; soma 282.
     qtd_tipo_principal  incidentes em que este código está em posicao = 1.
                         Soma exatamente 395: um tipo por incidente.
     qtd_envolvido       incidentes em que este código aparece em qualquer
                         posição. Soma 511: incidente com 2 tipos conta 2
                         vezes, uma em cada.
   Motivo: cada regra responde uma pergunta diferente, e nenhuma é "a
   certa". qtd_envolvido é a mais natural ("quantos incidentes envolvem
   roubo de credencial?") mas não fecha 100%; qtd_tipo_principal fecha 100%
   mas supõe que a ordem é prioridade, o que o dataset não documenta;
   qtd_tipo_unico ignora os 113 incidentes com mais de um tipo. Escolher uma
   só esconderia que CRED vai de 22 a 64 conforme a regra.
   O nome qtd_tipo_principal é uma suposição declarada, não um fato.

4. NATUREZA
   As três contagens do item 3 incluem todas as naturezas (incident,
   research, policy, vulnerability, report), como o qtd_incidentes original.
   Ao lado, qtd_envolvido_so_incidentes: a mesma regra de qtd_envolvido,
   só com natureza = 'incident'.
   Motivo: GOV é o primeiro do ranking em qtd_envolvido (67), mas só 2
   deles são incidentes; o resto é política e regulação. Sem essa coluna, o
   ranking de "ataques" é liderado por leis.

5. SEVERIDADE E DANO
   Todas sobre a base de qtd_envolvido (todas as naturezas):
     qtd_criticos            severidade = 'critical'
     qtd_dano_confirmado     dano_real = true
     qtd_dano_negado         dano_real = false
     qtd_dano_nao_se_aplica  dano_real nulo E natureza em (policy, report)
     qtd_dano_nao_informado  dano_real nulo em qualquer outra natureza
   Contagens, não percentuais.
   Motivo: percentual exige escolher denominador, e isso é decisão de quem
   lê. O rótulo do nulo vem da natureza, não do nulo, com a mesma regra de
   mart.evidencia: um incidente com dano nulo cai em nao_informado e fica
   visível. As quatro colunas de dano somam qtd_envolvido: o nulo ganha coluna
   própria em vez de sumir num percentual. O nulo são exatamente os
   registros de policy e report, onde "houve dano?" não se aplica, e isso
   não é "não houve dano" (GOV: 65 dos 67 são nulos, porque GOV é quase
   todo política).

6. COLUNAS, nesta ordem
   codigo, nome, qtd_tipo_unico, qtd_tipo_principal, qtd_envolvido,
   qtd_envolvido_so_incidentes, qtd_criticos, qtd_dano_confirmado,
   qtd_dano_negado, qtd_dano_nao_se_aplica, qtd_dano_nao_informado.
   Contagens como INTEGER. Ordenada por qtd_envolvido decrescente,
   desempate por codigo.

7. COMENTÁRIOS NO .sql
   Cabeçalho com a pergunta que o mart responde e o significado de cada
   regra do item 3. Comentários no meio só onde a decisão não é óbvia.

CRITÉRIOS DE ACEITE
- SELECT count(*) FROM mart.tipos_ataque = 12.
- Soma de qtd_tipo_unico = 282, de qtd_tipo_principal = 395, de
  qtd_envolvido = 511.
- qtd_tipo_unico = refined.tipos_ataque.qtd_incidentes nos 12 tipos.
- qtd_dano_confirmado + qtd_dano_negado + qtd_dano_nao_se_aplica +
  qtd_dano_nao_informado = qtd_envolvido em todas as linhas;
  qtd_dano_nao_informado = 0 em todas (hoje).
- CRED: 22 / 25 / 64, 45 só incidentes, 16 críticos, dano 43 / 21 / 0.
- GOV: 62 / 64 / 67, 2 só incidentes, dano 1 / 1 / 65.
- Rodar uv run python -m pipeline.marts duas vezes seguidas não muda o
  resultado.

ENTREGA, nesta ordem
1. A spec resumida como comentário no topo do .sql, dizendo por que cada
   regra existe.
2. O SQL.
3. Uma lista final do que você assumiu e que não estava na spec.
