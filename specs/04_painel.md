CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". As etapas 1 a 3 gravaram raw, refined e mart. Esta é a etapa 4: o
painel, que só mostra o que os marts já decidiram. Spec-driven: a spec
abaixo é a fonte da verdade e o código é consequência dela. Não acrescente
requisito que não esteja escrito aqui. Se algo estiver ambíguo, pergunte
antes de escrever código.

STACK
- Python 3.14, uv, DuckDB 2.x (incidentes.duckdb na raiz do projeto)
- streamlit e plotly (plotly.express), já no pyproject.toml

O QUE JÁ EXISTE (use, não reimplemente)
O schema mart, criado por pipeline/marts.py, com sete tabelas:
  tipos_ataque, tendencia_mensal, coocorrencia_ataques, evidencia,
  regioes, fontes, incidentes_painel.
Cada uma tem spec em specs/marts/NN_nome.md; as colunas e os motivos estão
lá, não aqui.

PRÉ-REQUISITO (falta, e vem antes do painel)
mart.kpis, de sql/marts/08_kpis.sql, com spec própria em
specs/marts/08_kpis.md. Uma linha, seis contagens INTEGER, todas as
naturezas:
  qtd_registros         todos os registros                         395
  qtd_incidentes        natureza = 'incident'                      162
  qtd_criticos          severidade = 'critical'                     48
  qtd_dano_confirmado   dano_real = true                           141
  qtd_contestados       contestado = true                           15
  qtd_fonte_unica       registros com exatamente uma URL           164
Motivo: nenhum mart atual guarda esses números numa célula só. Somar
mart.evidencia no painel seria regra de negócio fora do SQL (item 2).

ARTEFATOS A PRODUZIR
painel.py, na raiz: leitura, formatação, filtro da lista e gráficos. Não
  importa streamlit.
app.py, na raiz: a página. Executável com:
  uv run streamlit run app.py

SPEC

1. LEITURA (painel.py)
   ler(marts) -> dict nome -> DataFrame. Para cada nome, só
   SELECT * FROM mart.<nome>. Nenhuma outra SQL.
   Caminho do banco resolvido a partir da localização de painel.py, nunca
   do diretório corrente (a mesma regra D1 de pipeline/db.py).
   Conexão com duckdb.connect(<caminho>, read_only=True), aberta e fechada
   dentro de ler(). Não usa conectar() de pipeline/db.py.
   Motivo: conectar() cria o arquivo quando ele falta e abre para escrita;
   conexão aberta segura o arquivo, e pipeline.marts não consegue gravar
   com o painel de pé (o mesmo lock descrito em U2 do ui.py).

2. NENHUM CÁLCULO
   Proibido em painel.py e app.py: groupby, sum, mean, count, len sobre
   dados, merge, pivot, melt, value_counts, agregação do próprio plotly
   (histogram, density_heatmap) e qualquer conta entre colunas.
   Permitido: ordenar, filtrar linhas, head(n), escolher qual coluna
   plotar, renomear coluna e formatar texto.
   Motivo: número novo na tela exige um .sql novo em sql/marts/. Se faltar
   algum número, pare e diga qual mart está faltando.

3. LAYOUT (app.py), de cima para baixo, layout="wide"
   Cabeçalho: título "Incidentes de segurança com agentes de IA ·
     2024-26" à esquerda; à direita, o filtro de período (item 5) e a
     chave "Só incidentes" (item 6).
   Faixa 1: seis cartões (st.metric), nesta ordem, cada rótulo com a
     definição curta, valores de mart.kpis com numero():
       Registros · todas as naturezas           (qtd_registros)
       Incidentes · natureza incident           (qtd_incidentes)
       Críticos · severidade critical           (qtd_criticos)
       Dano confirmado · dano_real true         (qtd_dano_confirmado)
       Contestados · o próprio registro         (qtd_contestados)
       Fonte única · uma URL só                 (qtd_fonte_unica)
     Contagens, não percentuais. Motivo: os marts recusam percentual
     porque o denominador é decisão de quem lê; o painel não toma essa
     decisão escondido num cartão.
   Faixa 2, largura inteira: 02 · tendência mensal, linha com marcadores.
     Coluna y: total (ou qtd_incident com a chave do item 6).
     O ponto com mes_parcial = true leva a anotação "parcial".
     Motivo: specs/marts/02 manteve o mês parcial na série para não
     esconder registros; sem marca, a queda de 2026-10 parece real.
   Faixa 3, duas colunas iguais:
     01 · tipos de ataque: barras horizontais de qtd_envolvido, os 12
       tipos, maior em cima, rótulo = codigo, nome no hover.
     03 · coocorrência: matriz de pontos (px.scatter) com x = codigo_a,
       y = codigo_b, tamanho = qtd_juntos, as 66 linhas.
       Motivo: matriz sem pivot; o par com 0 fica como casa vazia, que é
       informação (specs/marts/03 item 3).
   Faixa 4, três colunas iguais:
     04 · situação do dano por natureza: barras horizontais empilhadas das
       quatro colunas qtd_dano_* (formato largo, sem melt), 5 naturezas,
       maior total em cima.
     05 · regiões: barras horizontais de qtd_envolvido, só as linhas com
       escopo diferente de 'global', maior em cima. Abaixo do gráfico, a
       legenda "GLOBAL: N registros, fora do gráfico", N lido da linha
       GLOBAL na mesma coluna plotada.
       Motivo: GLOBAL tem 321 e achata as outras 12 barras; o mart deixou
       o escopo declarado para quem lê filtrar, e o número não some.
     06 · fontes: top 10 domínios por qtd_registros, barras horizontais,
       maior em cima, desempate por dominio.
   Faixa 5, largura inteira: 07 · registros, tabela (item 7).
   Cada gráfico: título com o número do mart ("02 · Tendência mensal"),
   eixo com unidade ("registros", "incidentes", "pares"), uma cor só.
   Exceção: o 04 usa quatro tons da mesma cor, do mais escuro (confirmado)
   ao mais claro (nao_informado). Motivo: as quatro situações somam o
   total, e é a soma que a barra mostra.
   st.plotly_chart com width="stretch" (use_container_width está
   descontinuado).

4. FORMATO (painel.py), funções puras, sem streamlit e sem banco
   numero(valor, casas=0)   -> "1.234" / "4,09"
     Milhar com ponto, decimal com vírgula, sempre. Sem locale do sistema.
     Motivo: o resultado não pode depender da máquina de quem roda.
   data_texto(data, precisao) -> texto
     'day'            -> "09/10/2026"
     'month', 'part'  -> "10/2026"
     outro valor      -> "09/10/2026 (precisao)"
     Motivo: 53 registros têm o dia inventado (specs/marts/07 item 6);
     mostrar o dia deles é afirmar o que o dado não disse. Valor novo de
     precisao aparece em vez de ser tratado como 'day'.
   Uma função por gráfico, recebendo o DataFrame do mart (e a escolha do
   item 6) e devolvendo a figura plotly. Motivo: um relatório HTML futuro
   reaproveita as mesmas funções sem subir o Streamlit.

5. FILTRO DE PERÍODO
   st.select_slider com os meses de mart.tendencia_mensal, padrão do
   primeiro ao último (2024-12 a 2026-10), inclusive o mês parcial.
   Recorta só as linhas do gráfico 02 e da tabela 07 (pela coluna mes).
   Embaixo do filtro: "cartões e gráficos 01, 03 a 06 valem para o
   período inteiro".
   Motivo: recortar linha é filtro; recalcular cartão ou ranking por
   período seria regra de negócio fora do SQL.

6. CHAVE "SÓ INCIDENTES" (st.toggle, padrão desligado)
   Troca a coluna plotada, nunca filtra nem soma:
     01  qtd_envolvido        -> qtd_envolvido_so_incidentes
     02  total                -> qtd_incident
     03  qtd_juntos           -> qtd_juntos_so_incidentes
     05  qtd_envolvido        -> qtd_envolvido_so_incidentes
     06  qtd_registros        -> qtd_so_incidentes
   Com a chave ligada, os rankings são reordenados pela coluna nova
   (ordenar é permitido); o top 10 do 06 é refeito sobre ela.
   Não afeta os cartões nem o 04 (que já é por natureza) nem a tabela 07,
   e a página diz isso ao lado da chave.
   Motivo: todo mart guardou as duas leituras lado a lado e deixou a
   escolha para quem lê. Sem a chave, o ranking de ataques é liderado por
   GOV, que é quase todo política (specs/marts/01 item 4).

7. TABELA DE REGISTROS (07 · mart.incidentes_painel)
   filtrar_registros(df, naturezas, codigos, regioes, meses) em painel.py,
   função pura que devolve as linhas que passam em todos os filtros:
     naturezas  natureza está na lista
     codigos    codigos_ataque contém pelo menos um dos códigos
     regioes    regioes contém pelo menos uma das regiões
     meses      mes está no intervalo do item 5
   Lista vazia num filtro = filtro desligado.
   Motivo: "envolve X" é a regra qtd_envolvido de mart.tipos_ataque; o
   mart entregou listas para o filtro não reinventar o split.
   Filtros da página (st.multiselect, acima da tabela, vazios por padrão):
   natureza, tipo de ataque (opções e rótulos de mart.tipos_ataque),
   região (opções de mart.regioes).
   Colunas mostradas, nesta ordem: data (data_texto), titulo, natureza,
   severidade, confianca, situacao_dano, codigos_ataque, regioes,
   qtd_fontes. Listas como lista (st.column_config.ListColumn), não como
   texto com ';'. Ordem do mart (data decrescente).
   Sem contador de linhas filtradas. Motivo: é um count (item 2).

8. CACHE E ERRO
   Leitura com st.cache_data. Um botão "Recarregar dados" limpa o cache.
   Sem incidentes.duckdb: st.error com o caminho procurado e as três
   etapas, nesta ordem, e st.stop():
     uv run python -m pipeline.ingestao
     uv run python -m pipeline.transformacao
     uv run python -m pipeline.marts
   Motivo: sem banco não há raw nem refined; mandar rodar só os marts leva
   ao erro de "tabelas faltando em refined" do pipeline.marts.
   Banco presente, faltando qualquer um dos oito marts (os sete atuais e
   kpis): st.error dizendo quais e o comando
   "uv run python -m pipeline.marts", e st.stop().
   Banco travado por outro processo (pipeline.marts gravando): st.error
   dizendo que o pipeline está rodando e para clicar em "Recarregar dados"
   quando ele terminar, e st.stop(). Sem traceback na tela.
   Motivo: um painel com metade dos marts mostra um dado errado que parece
   certo.

CRITÉRIOS DE ACEITE
- Os seis cartões mostram: 395 · 162 · 48 · 141 · 15 · 164.
- O 02 abre com 23 pontos (2024-12 a 2026-10), pico de 80 em 2026-09 e
  "parcial" em 2026-10. Com a chave ligada, o pico vira 32.
- 01: GOV em cima (67). Com a chave ligada: CRED em cima (45), GOV com 2.
- 03: 66 pontos possíveis; o maior é EXFIL × IPI (24). Com a chave
  ligada: CRED × SUPPLY (18).
- 04: policy (72) e report (15) inteiros em nao_se_aplica.
- 05: 12 barras, US em cima (36), legenda "GLOBAL: 321 registros". Com a
  chave ligada: US com 20, legenda com 118.
- 06: thehackernews.com em cima (55), darkreading.com em décimo (12). Com
  a chave ligada: thehackernews.com (21) e bleepingcomputer.com (15) nos
  dois primeiros.
- filtrar_registros com codigos=['CRED'] devolve 64 linhas, o
  qtd_envolvido de CRED; com naturezas=['incident'], 162.
- data_texto de um registro com precisao_data 'month' não mostra dia.
- Uma busca por "groupby", ".sum(", ".mean(", ".count(", "len(", "merge",
  "pivot" e "melt" em painel.py e app.py não encontra nada.
- painel.py não importa streamlit.
- Com o painel de pé, uv run python -m pipeline.marts roda sem erro de
  lock; "Recarregar dados" mostra o resultado novo.
- Renomear incidentes.duckdb faz o painel mostrar o st.error, sem criar
  arquivo novo.

ENTREGA
1. A spec como docstring no topo de painel.py, com o motivo de cada regra.
2. O código, comentado só onde a decisão não é óbvia.
3. Uma lista final do que você assumiu e que não estava na spec.
