CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". A etapa 2 separou a coluna regioes na ponte
refined.incidente_regioes. Este mart conta por região e decide como tratar
GLOBAL e os rótulos de escalas diferentes. Spec-driven: a spec é a fonte da
verdade. Não acrescente requisito que não esteja escrito aqui. Se algo
estiver ambíguo, pergunte antes de escrever código.

PERGUNTA QUE O MART RESPONDE
Onde acontece — e quanto do dado permite responder isso?

STACK
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Arquivo .sql em sql/marts/ com um único SELECT; pipeline/marts.py o
  grava como tabela (specs/03_marts.md).

O QUE JÁ EXISTE (use, não reimplemente)
refined.incidente_regioes  (incidente_id, posicao, regiao)          409 linhas
refined.incidentes         (incidente_id, regioes, natureza,
                            severidade, dano_real, ...)             395 linhas

ARTEFATO A PRODUZIR
sql/marts/05_regioes.sql: um único SELECT (pode começar com comentários
e WITH), gravado como tabela mart.regioes por uv run python -m pipeline.marts.

SPEC

1. FORMA
   Um único SELECT, sem CREATE: pipeline.marts grava o resultado como
   tabela mart.regioes (specs/03_marts.md). Lê só de refined.
   Motivo: a regra de negócio mora inteira no .sql; quem cria, recria e
   apaga tabelas é o pipeline, numa transação só.

2. GRÃO
   Uma linha por região que aparece em refined.incidente_regioes: 13 hoje.
   Motivo: não existe tabela de regiões na fonte, então não há lista de
   "regiões possíveis" para mostrar com 0, como os tipos de ataque têm.

3. GLOBAL FICA, COM ESCOPO DECLARADO
   GLOBAL é uma linha como as outras. Ao lado, a coluna escopo:
     global    GLOBAL
     regional  EU, LATAM, SEA, APAC  (blocos e regiões do mundo)
     local     US, CN, JP, KR, AU, TW, UK, HK
     nao_classificado  qualquer código fora das três listas (hoje nenhum)
   As três listas são fixas no SQL.
   Motivo de nao_classificado: um código novo na fonte (ex.: 'MENA') não
   pode virar local em silêncio; com rótulo próprio, aparece — a mesma
   regra de qtd_dano_nao_informado.
   Motivo: GLOBAL está em 321 das 409 marcações; tirá-lo apagaria 310
   registros que a fonte classificou, e mantê-lo sem marca faz um mapa
   pintar "GLOBAL" ao lado de "US" como se fossem a mesma escala. O escopo
   deixa quem lê filtrar. "local" e não "país" porque HK e TW não são
   classificados aqui como países ou não — o mart não decide geopolítica.
   Nenhum código é fundido em outro: HK não vira CN, EU não se expande em
   países. Motivo: a fonte marcou HK quando quis HK.

4. CONTAGENS, lado a lado
     qtd_envolvido                registros que têm esta região, em qualquer
                                  posição. Soma 409, não 395: um registro
                                  com 'CN;GLOBAL' conta nas duas.
     qtd_regiao_unica             registros cujo regioes é só esta região
     qtd_com_global               registros com esta região E GLOBAL
                                  (0 na própria linha GLOBAL)
     qtd_envolvido_so_incidentes  qtd_envolvido só com natureza = 'incident'
     qtd_criticos                 qtd_envolvido com severidade = 'critical'
     qtd_dano_confirmado          qtd_envolvido com dano_real = true
   Motivo: as mesmas regras de contagem de mart.tipos_ataque (envolvido x
   única), pelo mesmo motivo: escolher uma esconderia que CN vai de 10 a
   20. qtd_com_global existe porque 8 dos 20 de CN são 'CN;GLOBAL': origem
   chinesa com alcance global, que não é o mesmo que um caso só na China.
   qtd_dano_confirmado sozinho, sem as outras situações de dano: é uma
   contagem, não um percentual, então nenhum nulo some; o detalhe de dano
   está em mart.evidencia.

5. COLUNAS, nesta ordem
   regiao, escopo, qtd_envolvido, qtd_regiao_unica, qtd_com_global,
   qtd_envolvido_so_incidentes, qtd_criticos, qtd_dano_confirmado.
   regiao e escopo VARCHAR, contagens INTEGER. Ordenada por qtd_envolvido
   decrescente, desempate por regiao.

6. COMENTÁRIOS NO .sql
   Cabeçalho com a pergunta que o mart responde e o porquê de cada regra.
   Comentários no meio só onde a decisão não é óbvia.

LIMITE CONHECIDO (não é requisito, é aviso para quem lê)
   Fora de GLOBAL, só US (36) e CN (20) passam de 9 registros. O mart
   responde "onde" para cerca de 85 registros; o resto a fonte marcou como
   global.

CRITÉRIOS DE ACEITE
- 13 linhas; sum(qtd_envolvido) = 409.
- escopo: 1 global, 4 regional, 8 local, 0 nao_classificado.
- GLOBAL: 321 envolvido, 310 única, 118 só incidentes.
- CN: 20 envolvido, 10 única, 8 com GLOBAL.
- sum(qtd_regiao_unica) = 381 (os 395 menos os 14 com mais de uma região).
- qtd_regiao_unica <= qtd_envolvido e qtd_com_global <= qtd_envolvido em
  todas as linhas.
- Rodar uv run python -m pipeline.marts duas vezes seguidas não muda o
  resultado.

ENTREGA, nesta ordem
1. A spec resumida como comentário no topo do .sql, dizendo por que cada
   regra existe.
2. O SQL.
3. Uma lista final do que você assumiu e que não estava na spec.
