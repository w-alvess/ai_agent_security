CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". O painel (specs/04_painel.md) não faz conta: todo número na tela
vem pronto de um mart. Os cartões do topo precisam de seis totais que
nenhum mart guarda numa célula só. Este mart os entrega, sem decisão nova:
aplica as regras que os outros marts já escreveram. Spec-driven: a spec é a
fonte da verdade. Não acrescente requisito que não esteja escrito aqui. Se
algo estiver ambíguo, pergunte antes de escrever código.

PERGUNTA QUE O MART RESPONDE
Qual é o tamanho do dado — e quanto dele é incidente, crítico, com dano
confirmado, contestado ou apoiado numa fonte só?

STACK
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Arquivo .sql em sql/marts/ com um único SELECT; pipeline/marts.py o
  grava como tabela (specs/03_marts.md).

O QUE JÁ EXISTE (use, não reimplemente)
refined.incidentes  (incidente_id, natureza, severidade, dano_real,
                     contestado, ...)                         395 linhas
refined.fontes      (incidente_id, posicao, url)              797 linhas
mart.evidencia, mart.tendencia_mensal   só conferência (critérios de aceite)

ARTEFATO A PRODUZIR
sql/marts/08_kpis.sql: um único SELECT (pode começar com comentários e
WITH), gravado como tabela mart.kpis por uv run python -m pipeline.marts.

SPEC

1. FORMA
   Um único SELECT, sem CREATE: pipeline.marts grava o resultado como
   tabela mart.kpis (specs/03_marts.md). Lê só de refined.
   Motivo: a regra de negócio mora inteira no .sql; quem cria, recria e
   apaga tabelas é o pipeline, numa transação só.
   Não lê de outro mart, mesmo que mart.evidencia já tenha quase tudo.
   Motivo: a ordem dos arquivos fica irrelevante (a mesma regra de
   specs/marts/03); bater com evidencia e tendencia_mensal vira
   conferência, não dependência.

2. GRÃO
   Uma linha só. Motivo: são os totais do dado inteiro; o painel lê cada
   cartão de uma célula, sem filtrar nem somar.

3. CONTAGENS (todas as naturezas, salvo qtd_incidentes)
     qtd_registros         todos os registros de refined.incidentes
     qtd_incidentes        natureza = 'incident'
     qtd_criticos          severidade = 'critical'
     qtd_dano_confirmado   dano_real = true
     qtd_contestados       contestado = true
     qtd_fonte_unica       registros com exatamente uma linha em
                           refined.fontes
   Motivo de todas as naturezas: o painel mostra qtd_registros e
   qtd_incidentes lado a lado, e a distância entre os dois é a informação
   (233 dos 395 não são incidentes). Cortar por natureza aqui seria
   decidir pelo painel o que é "incidente", a decisão que
   mart.tipos_ataque e mart.tendencia_mensal se recusaram a tomar.
   qtd_fonte_unica com a mesma regra de mart.evidencia: registro sem
   nenhuma URL não conta como fonte única (hoje nenhum).

4. O QUE NÃO SE FAZ AQUI
   Nenhum percentual. Motivo: percentual exige escolher denominador
   (registros? incidentes?), e isso é de quem lê, como nos outros marts.
   Nenhuma contagem de dano negado ou nulo: o detalhe de dano está em
   mart.evidencia; o cartão mostra só o confirmado, que é contagem e não
   esconde nenhum nulo.
   Nenhum recorte por período: o filtro de período do painel não muda os
   cartões (specs/04_painel.md item 5).

5. COLUNAS, nesta ordem
   qtd_registros, qtd_incidentes, qtd_criticos, qtd_dano_confirmado,
   qtd_contestados, qtd_fonte_unica. Todas INTEGER.

6. COMENTÁRIOS NO .sql
   Cabeçalho com a pergunta que o mart responde e o porquê de cada regra.
   Comentários no meio só onde a decisão não é óbvia.

CRITÉRIOS DE ACEITE
- 1 linha: 395 · 162 · 48 · 141 · 15 · 164.
- Conferência com os outros marts:
    qtd_registros       = sum(mart.evidencia.total)
    qtd_incidentes      = mart.evidencia.total na linha 'incident'
    qtd_criticos        = sum(mart.tendencia_mensal.qtd_criticos)
    qtd_dano_confirmado = sum(mart.evidencia.qtd_dano_confirmado)
    qtd_contestados     = sum(mart.evidencia.qtd_contestado)
    qtd_fonte_unica     = sum(mart.evidencia.qtd_fonte_unica)
- uv run python -m pipeline.marts passa a gravar oito marts, com
  mart.kpis 1 linha. Total: 818.
- Rodar uv run python -m pipeline.marts duas vezes seguidas não muda o
  resultado.

ENTREGA, nesta ordem
1. A spec resumida como comentário no topo do .sql, dizendo por que cada
   regra existe.
2. O SQL.
3. Uma lista final do que você assumiu e que não estava na spec.
