CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". A etapa 2 separou a coluna sources na ponte refined.fontes (797
linhas, 724 URLs distintas). Este mart agrupa as URLs por domínio e mede
quanto do dado depende de cada um. Spec-driven: a spec é a fonte da
verdade. Não acrescente requisito que não esteja escrito aqui. Se algo
estiver ambíguo, pergunte antes de escrever código.

PERGUNTA QUE O MART RESPONDE
De onde vem a informação — e quanto do dado depende de um domínio só?

STACK
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Arquivo .sql em sql/marts/ com um único SELECT; pipeline/marts.py o
  grava como tabela (specs/03_marts.md).

O QUE JÁ EXISTE (use, não reimplemente)
refined.fontes      (incidente_id, posicao, url)            797 linhas
refined.incidentes  (incidente_id, natureza, ...)           395 linhas

ARTEFATO A PRODUZIR
sql/marts/06_fontes.sql: um único SELECT (pode começar com comentários
e WITH), gravado como tabela mart.fontes por uv run python -m pipeline.marts.

SPEC

1. FORMA
   Um único SELECT, sem CREATE: pipeline.marts grava o resultado como
   tabela mart.fontes (specs/03_marts.md). Lê só de refined.
   Motivo: a regra de negócio mora inteira no .sql; quem cria, recria e
   apaga tabelas é o pipeline, numa transação só.

2. DOMÍNIO (a decisão central deste mart)
   dominio = host da URL (entre '://' e o primeiro '/', ':', '?' ou '#'),
   em minúsculas, sem o 'www.' do início. Nada mais é juntado.
   URL sem host reconhecível: dominio = 'nao_identificado' (hoje nenhuma).
   Motivo: juntar subdomínios (blogs.microsoft.com em microsoft.com)
   exige saber onde termina o sufixo, e 11 hosts usam sufixo de dois
   níveis (finance.sina.com.cn, www.aisi.gov.uk); a regra "dois últimos
   pedaços" os transformaria em com.cn e gov.uk. Uma lista de sufixos
   mantida à mão erra em silêncio no primeiro sufixo novo. Host sem
   'www.' é previsível e nunca junta errado.
   Custo aceito: a mesma organização pode aparecer em mais de uma linha
   (anthropic.com, www-cdn.anthropic.com, red.anthropic.com).

3. GRÃO
   Uma linha por domínio: 303 hoje (305 hosts; www.anthropic.com e
   www.darkreading.com se juntam às versões sem www).

4. CONTAGENS, lado a lado
     qtd_citacoes         linhas de refined.fontes com este domínio
                          (soma 797)
     qtd_registros        registros distintos que citam o domínio
     qtd_urls             URLs distintas do domínio
     qtd_so_incidentes    qtd_registros só com natureza = 'incident'
     qtd_como_primeira    registros em que o domínio está em posicao = 1
                          (soma 395: uma primeira fonte por registro)
     qtd_fonte_exclusiva  registros cujas fontes são todas deste domínio
                          (soma 166: os registros com um domínio só)
   Motivo: qtd_citacoes e qtd_registros diferem quando um registro cita o
   mesmo domínio mais de uma vez (github.com: 25 e 23). qtd_registros
   maior que qtd_urls denuncia compilação: uma URL servindo de fonte para
   vários registros (genai.owasp.org: 22 registros em 8 URLs).
   qtd_fonte_exclusiva mede dependência: quanto do dado cai se aquele
   domínio estiver errado (genai.owasp.org: 20).
   qtd_como_primeira é contagem de posição, não afirmação de que a
   primeira é a principal — a mesma ressalva de qtd_tipo_principal.

5. O QUE NÃO SE FAZ AQUI
   Nenhuma classificação de domínio (imprensa, fornecedor, governo):
   são 303 domínios e a classificação seria opinião mantida à mão.
   Nenhuma marca de "fonte do próprio fornecedor": o dado não diz de qual
   empresa é cada incidente, então não há com o que comparar o domínio.

6. COLUNAS, nesta ordem
   dominio, qtd_citacoes, qtd_registros, qtd_urls, qtd_so_incidentes,
   qtd_como_primeira, qtd_fonte_exclusiva.
   dominio VARCHAR, contagens INTEGER. Ordenada por qtd_registros
   decrescente, desempate por dominio.

7. COMENTÁRIOS NO .sql
   Cabeçalho com a pergunta que o mart responde e o porquê de cada regra.
   Comentários no meio só onde a decisão não é óbvia.

CRITÉRIOS DE ACEITE
- 303 linhas; nenhum dominio começa com 'www.'; nenhum 'nao_identificado'.
- sum(qtd_citacoes) = 797; sum(qtd_urls) = 724;
  sum(qtd_como_primeira) = 395; sum(qtd_fonte_exclusiva) = 166.
- thehackernews.com: 55 citações, 55 registros, 21 só incidentes.
- genai.owasp.org: 22 registros, 8 URLs, 20 com fonte exclusiva.
- anthropic.com: 21 citações (as de www.anthropic.com incluídas);
  www-cdn.anthropic.com continua linha separada.
- Em todas as linhas: qtd_registros, qtd_urls <= qtd_citacoes;
  qtd_so_incidentes, qtd_como_primeira, qtd_fonte_exclusiva <=
  qtd_registros.
- Rodar uv run python -m pipeline.marts duas vezes seguidas não muda o
  resultado.

ENTREGA, nesta ordem
1. A spec resumida como comentário no topo do .sql, dizendo por que cada
   regra existe.
2. O SQL.
3. Uma lista final do que você assumiu e que não estava na spec.
