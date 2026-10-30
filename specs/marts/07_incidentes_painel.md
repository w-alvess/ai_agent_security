CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". Os outros marts agregam; este é o único no grão do registro, para
o painel (Streamlit) filtrar e listar. Ele não toma decisão nova: aplica as
que os outros marts já escreveram. Spec-driven: a spec é a fonte da
verdade. Não acrescente requisito que não esteja escrito aqui. Se algo
estiver ambíguo, pergunte antes de escrever código.

PERGUNTA QUE O MART RESPONDE
Quais são os registros, um a um, com tudo o que o painel precisa para
filtrar sem refazer JOIN nem split?

STACK
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Arquivo .sql em sql/marts/ com um único SELECT; pipeline/marts.py o
  grava como tabela (specs/03_marts.md).

O QUE JÁ EXISTE (use, não reimplemente)
refined.incidentes, refined.tipos_ataque, refined.incidente_tipos,
refined.incidente_regioes, refined.fontes.

ARTEFATO A PRODUZIR
sql/marts/07_incidentes_painel.sql: um único SELECT (pode começar com comentários
e WITH), gravado como tabela mart.incidentes_painel por uv run python -m pipeline.marts.

SPEC

1. FORMA
   Um único SELECT, sem CREATE: pipeline.marts grava o resultado como
   tabela mart.incidentes_painel (specs/03_marts.md). Lê só de refined.
   Motivo: a regra de negócio mora inteira no .sql; quem cria, recria e
   apaga tabelas é o pipeline, numa transação só.

2. GRÃO
   Uma linha por registro: 395, todas as naturezas.
   Motivo: o painel filtra por natureza; cortar aqui seria decidir pelo
   painel o que é "incidente" — a decisão que mart.tipos_ataque e
   mart.tendencia_mensal se recusaram a tomar.

3. LISTAS EM VEZ DE STRING COM ';'
   codigos_ataque, nomes_ataque, regioes e urls_fontes são LIST
   (VARCHAR[]), na ordem de posicao das pontes.
   nomes_ataque vem de refined.tipos_ataque, alinhado com codigos_ataque;
   código sem nome vira NULL na mesma posição (hoje nenhum).
   Motivo: o filtro do painel é "registros que envolvem X"
   (list_contains), a regra qtd_envolvido de mart.tipos_ataque; com
   string, cada filtro reinventaria o split ou usaria LIKE, que confunde
   códigos que são pedaço de outros. No pandas, a lista chega como array.
   Não há coluna de tipo principal. Motivo: ela supõe que a ordem é
   prioridade, e o dataset não documenta isso.
   Coluna multivalor nula em refined vira lista nula, não lista vazia
   (hoje nenhuma). Motivo: lista vazia afirmaria "nenhum tipo"; nulo diz
   "não informado".

4. situacao_dano
   'confirmado' (dano_real true), 'negado' (false), 'nao_se_aplica' (nulo
   em policy ou report), 'nao_informado' (nulo em outra natureza).
   Motivo: a mesma regra de mart.evidencia e mart.tipos_ataque; um rótulo
   em vez de BOOLEAN nulo, porque o painel mostra texto e o nulo de uma
   lei não é o mesmo nulo de um incidente.

5. SÓ TEXTO EM INGLÊS
   titulo e resumo; as traduções e os caminhos ficam fora.
   Motivo: o painel é em uma língua. As traduções continuam em
   refined.incidentes para quem precisar — nada foi apagado, só não
   entra neste recorte.

6. COLUNAS, nesta ordem
   incidente_id, data, precisao_data, data_fim, mes, titulo, resumo,
   natureza, severidade, confianca, envolvimento_ia, contestado, marco,
   situacao_dano, codigos_ataque, nomes_ataque, regioes, urls_fontes,
   qtd_fontes.
   Tipos como em refined; listas VARCHAR[]; qtd_fontes INTEGER
   (= len(urls_fontes)). precisao_data vai junto com data. Motivo: 53
   datas têm dia inventado, e o painel precisa poder mostrar isso.
   Ordenada por data decrescente, desempate por incidente_id.

7. COMENTÁRIOS NO .sql
   Cabeçalho com o porquê de cada regra. Comentários no meio só onde a
   decisão não é óbvia.

CRITÉRIOS DE ACEITE
- 395 linhas, incidente_id único.
- situacao_dano: 141 confirmado, 167 negado, 87 nao_se_aplica,
  0 nao_informado.
- Soma de len(codigos_ataque) = 511, de len(regioes) = 409,
  de qtd_fontes = 797.
- array_to_string(lista, ';') devolve exatamente a string de
  refined.incidentes, nas três listas e em todas as linhas.
- Nenhum NULL dentro de nomes_ataque; nenhuma lista nula.
- list_contains(codigos_ataque, 'CRED') seleciona 64 registros, o
  qtd_envolvido de CRED em mart.tipos_ataque.
- Rodar uv run python -m pipeline.marts duas vezes seguidas não muda o
  resultado.

ENTREGA, nesta ordem
1. A spec resumida como comentário no topo do .sql, dizendo por que cada
   regra existe.
2. O SQL.
3. Uma lista final do que você assumiu e que não estava na spec.
