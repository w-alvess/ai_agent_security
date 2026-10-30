CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". Cada registro traz quatro sinais de quanto ele é sólido:
confianca (A a D), envolvimento_ia, contestado e dano_real, além do número
de fontes (refined.fontes). Este mart junta os quatro sinais lado a lado.
Spec-driven: a spec é a fonte da verdade. Não acrescente requisito que não
esteja escrito aqui. Se algo estiver ambíguo, pergunte antes de escrever
código.

PERGUNTA QUE O MART RESPONDE
Quanto disso é confirmado — e a resposta muda conforme o tipo de registro?

STACK
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Arquivo .sql em sql/marts/ com um único SELECT; pipeline/marts.py o
  grava como tabela (specs/03_marts.md).

O QUE JÁ EXISTE (use, não reimplemente)
refined.incidentes  (incidente_id, natureza, confianca, envolvimento_ia,
                     contestado, dano_real, ...)                 395 linhas
refined.fontes      (incidente_id, posicao, url)                 797 linhas

ARTEFATO A PRODUZIR
sql/marts/04_evidencia.sql: um único SELECT (pode começar com comentários
e WITH), gravado como tabela mart.evidencia por uv run python -m pipeline.marts.

SPEC

1. FORMA
   Um único SELECT, sem CREATE: pipeline.marts grava o resultado como
   tabela mart.evidencia (specs/03_marts.md). Lê só de refined.
   Motivo: a regra de negócio mora inteira no .sql; quem cria, recria e
   apaga tabelas é o pipeline, numa transação só.

2. GRÃO
   Uma linha por natureza: 5 linhas (incident, research, policy,
   vulnerability, report).
   Motivo: os sinais de evidência significam coisas diferentes conforme a
   natureza — dano não existe numa lei, e 33 incidentes sem dano são
   quase-acidentes, enquanto 86 pesquisas sem dano são o esperado. Somar
   tudo numa linha só misturaria as cinco leituras.

3. SITUAÇÃO DO DANO (a decisão central deste mart)
   dano_real vira quatro contagens, que somam total:
     qtd_dano_confirmado      dano_real = true
     qtd_dano_negado          dano_real = false
     qtd_dano_nao_se_aplica   dano_real nulo E natureza em (policy, report)
     qtd_dano_nao_informado   dano_real nulo em qualquer outra natureza
   Hoje os 87 nulos são exatamente os 72 policy + 15 report, e
   qtd_dano_nao_informado é 0 em todas as linhas.
   Motivo: lei e relatório não têm dano; a pergunta não se aplica. O
   rótulo vem da natureza, não do nulo: se um dia aparecer um incidente
   com dano_real nulo, ele cai em nao_informado e fica visível, em vez de
   ser rotulado "não se aplica" só por ser nulo.

4. OS OUTROS SINAIS, lado a lado, todos contagens que somam total:
   confianca:        qtd_confianca_a, _b, _c, _d
   envolvimento_ia:  qtd_ia_confirmada ('confirmed'),
                     qtd_ia_contestada ('disputed'),
                     qtd_ia_nao_verificada ('unverified'),
                     qtd_ia_nao_se_aplica ('not-applicable')
   contestado:       qtd_contestado (true); o complemento é total menos ele
   fontes:           qtd_fonte_unica (1 URL), qtd_varias_fontes (2 ou mais)
   Motivo: contagens e não percentual, como nos outros marts. Nenhum
   índice composto ("evidência forte" = A + confirmado + não contestado):
   combinar os sinais é decidir o peso de cada um, e isso é de quem lê.
   contestado e envolvimento_ia ficam separados porque não dizem a mesma
   coisa: 8 registros contestados têm envolvimento de IA 'confirmed' (o
   que se contesta é outra parte do fato).

5. COLUNAS, nesta ordem
   natureza, total, qtd_confianca_a, qtd_confianca_b, qtd_confianca_c,
   qtd_confianca_d, qtd_ia_confirmada, qtd_ia_contestada,
   qtd_ia_nao_verificada, qtd_ia_nao_se_aplica, qtd_contestado,
   qtd_dano_confirmado, qtd_dano_negado, qtd_dano_nao_se_aplica,
   qtd_dano_nao_informado, qtd_fonte_unica, qtd_varias_fontes.
   natureza VARCHAR, contagens INTEGER. Ordenada por total decrescente.

6. COMENTÁRIOS NO .sql
   Cabeçalho com a pergunta que o mart responde e o porquê de cada regra.
   Comentários no meio só onde a decisão não é óbvia.

CRITÉRIOS DE ACEITE
- 5 linhas; sum(total) = 395.
- Em todas as linhas, cada grupo soma total: as 4 de confiança, as 4 de
  envolvimento, as 4 de dano, as 2 de fontes. (Um valor novo de confianca
  ou envolvimento_ia na fonte quebra este critério — é ele que avisa.)
- incident: 162 no total, dano 129 / 33 / 0 / 0, confiança A 132,
  9 contestados, 60 com fonte única.
- policy: 72, todos em qtd_dano_nao_se_aplica. report: 15, idem.
- sum(qtd_dano_nao_se_aplica) = 87; sum(qtd_dano_nao_informado) = 0.
- sum(qtd_contestado) = 15; sum(qtd_fonte_unica) = 164.
- Rodar uv run python -m pipeline.marts duas vezes seguidas não muda o
  resultado.

ENTREGA, nesta ordem
1. A spec resumida como comentário no topo do .sql, dizendo por que cada
   regra existe.
2. O SQL.
3. Uma lista final do que você assumiu e que não estava na spec.
