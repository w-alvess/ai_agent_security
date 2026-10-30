CONTEXTO
Pipeline sobre o dataset "AI Agent Security and Real-World Incidents
2024-26". As etapas 1 a 4 existem: ingestão, transformação, marts e painel.
Esta é a etapa 5: os testes unitários do código. Spec-driven: a spec abaixo
é a fonte da verdade e o código é consequência dela. Não acrescente
requisito que não esteja escrito aqui. Se algo estiver ambíguo, pergunte
antes de escrever código.

STACK
- Python 3.14, uv, DuckDB 2.x
- pytest e pytest-cov, já no grupo dev do pyproject.toml

O QUE JÁ EXISTE (leia tudo antes de escrever qualquer teste)
pipeline/db.py, pipeline/ingestao.py, pipeline/transformacao.py,
pipeline/marts.py, painel.py, app.py, ui.py, scripts/download_data.py e
sql/marts/*.sql. Cada módulo tem a sua spec na docstring do topo; os
critérios de aceite completos estão em specs/01 a 04 e specs/marts/*.md.

ARTEFATOS A PRODUZIR
Pasta test/ na raiz, com um arquivo por módulo: test_db.py,
test_ingestao.py, test_transformacao.py, test_marts.py, test_painel.py e
test_sql_marts.py (os .sql do item 4). Executável com:
  uv run pytest --cov
Configuração no pyproject.toml:
  [tool.pytest.ini_options]
  testpaths = ["test"]
  pythonpath = ["."]
  [tool.coverage.run]
  source = ["."]
  omit = ["test/*", "app.py", "ui.py", "scripts/*", ".venv/*"]
  [tool.coverage.report]
  fail_under = 60
  show_missing = true

SPEC
1. META
   60% de coverage de linhas no TOTAL do código Python do projeto:
   pipeline/ e painel.py. A meta é do total, não de cada arquivo. Arquivo
   que nenhum teste importa conta como 0%, e é isso que o source = ["."]
   garante.
   Ficam fora da medição:
     app.py                a tela do Streamlit, conferida no navegador com
                           os critérios de aceite de specs/04_painel.md.
                           Testar layout por coverage não prova nada.
     ui.py                 só abre a interface do DuckDB e fica de pé até
                           Ctrl+C.
     scripts/download_data.py  baixa do Kaggle; testar exigiria rede ou
                           mock do kagglehub, e o mock só provaria o mock.

2. NUNCA O BANCO NEM OS DADOS DO PROJETO
   Nenhum teste abre o incidentes.duckdb da raiz nem lê os arquivos de
   data/raw/. Cada teste usa tmp_path: um DuckDB novo dentro dele e, quando
   precisar de CSV, arquivos .csv pequenos escritos pelo próprio teste.
   Motivo: o teste tem que rodar em qualquer máquina, sem o pipeline ter
   rodado e sem o dataset baixado, e não pode alterar o banco de ninguém.

   monkeypatch.chdir NÃO basta: pela regra D1, todo caminho é resolvido a
   partir da localização do arquivo, nunca do diretório corrente. Use
   monkeypatch.setattr nestas constantes, e só nelas:
     pipeline.db._BANCO          conectar() lê na hora da chamada; vale
                                 para ingestão, transformação e marts, que
                                 importam conectar()
     pipeline.ingestao.PASTA_RAW importado com "from ... import"; trocar
                                 pipeline.db.PASTA_RAW não chega à ingestão
     pipeline.marts.PASTA_MARTS  só nos testes de pipeline.marts
     painel.BANCO
   Um teste que chama conectar(), main() ou ler() sem a troca acima abre o
   banco do projeto. O critério de aceite com o banco renomeado existe para
   pegar esse esquecimento.

   Os .sql de sql/marts/ são código, não dado: test_sql_marts.py lê esses
   arquivos do projeto e os executa sobre tabelas refined inventadas.

   São testes unitários do código. Testes de qualidade sobre o dado real
   (chave única, domínio, totais que batem com refined.tendencia_mensal)
   ficam fora deste pedido.

3. DADO INVENTADO, RESULTADO DA REGRA
   Toda entrada é inventada pelo teste: poucas linhas, cada uma com um
   comentário dizendo por que está ali (incidente com dois tipos, registro
   de natureza policy com dano nulo, mês sem nenhum registro, data com
   precisão 'month', linha inteira repetida, 'NA' numa coluna de região).
   O valor esperado sai da conta feita sobre essa entrada, nunca de um
   número medido no dado real (395, 724, 162, 511, 321...).
   Motivo: o dado real muda a cada versão do dataset; a regra não.
   As tabelas inventadas têm só as colunas que o código ou o .sql lê.
   Exceção: raw.incidentes_completo precisa das 31 colunas, porque a
   transformação seleciona todas; a lista de nomes pode vir do mapa
   TABELAS do módulo, os valores e os asserts nunca.

4. O QUE TESTAR
   Os critérios de aceite das docstrings e das specs são a lista de
   partida: cada critério que descreve uma regra vira pelo menos um teste.
   Critério que é um número do dado real vira a regra que o produz, sobre
   dado inventado. Em especial:
   - db: conectar() cria o arquivo em _BANCO, não na pasta corrente;
     PASTA_RAW é <pasta acima de pipeline/>/data/raw, com a pasta corrente
     em outro lugar; gravar() de 3 linhas devolve 3, e de novo 3; coluna
     str vira VARCHAR e None vira NULL; nenhuma view sobra depois.
   - ingestão: cada CSV vira tabela com as mesmas linhas, linha repetida
     inclusive; toda coluna VARCHAR, mesmo com "2024" e "True"; "NA" continua
     texto e campo vazio vira NULL, não ''; texto em chinês chega intacto;
     rodar duas vezes dá as mesmas contagens; sources_bibliography.txt
     ausente não muda nada; arquivo faltando encerra com SystemExit antes
     de criar o banco.
   - transformação: duplicata exata sai e a tela diz quantas saíram; chave
     repetida com conteúdo diferente encerra; data vira DATE, dano_real,
     contestado e marco BOOLEAN, contagens INTEGER, mes continua VARCHAR;
     'yes' num booleano, data fora de '%Y-%m-%d' e inteiro inválido
     encerram com SystemExit, sem virar nulo e sem gravar nada; dano_real
     nulo continua nulo, não false; 'IPI;EXFIL' vira duas linhas na ponte,
     posicao 1 e 2, e a string original fica em refined.incidentes; pedaço
     vazio ('IPI;') encerra; nada de trim (' EXFIL' chega com o espaço);
     raw.incidentes não vira refined; raw fica intacto; tabela faltando em
     raw encerra.
   - marts: arquivo sem prefixo NN_ para antes de executar qualquer SQL;
     dois arquivos com o mesmo nome de tabela param; pasta sem .sql para;
     tabela de refined faltando para; 00_teste.sql com "SELECT 1 AS x;"
     vira mart.teste com 1 linha (prefixo e ponto e vírgula tirados); .sql
     com erro e mart vazio encerram e deixam o schema mart como estava;
     arquivo apagado faz o mart sumir na execução seguinte; contagem na
     tela com milhar com ponto (um SELECT de range(1500) mostra "1.500").
   - sql/marts 01, 02, 03 e 08, rodados sobre refined inventado:
       01  incidente com dois tipos conta uma vez em qtd_tipo_principal e
           uma em qtd_envolvido de cada tipo, e fica fora de
           qtd_tipo_unico; tipo sem incidente aparece com 0; dano nulo em
           policy é nao_se_aplica, em incident é nao_informado.
       02  mês sem registro aparece com 0; mes_parcial só no mês da maior
           data, e só se ela não for o último dia do mês; incidente com
           data_fim conta uma vez, no mês de início.
       03  incidente com três tipos gera três pares; par sempre com
           codigo_a < codigo_b; par que nunca aparece junto vem com 0.
       08  registro sem nenhuma URL fica fora de qtd_fonte_unica.
     04 a 07 ficam fora deste pedido.
   - painel: numero() com inteiro, com casas decimais e com milhão;
     data_texto() com 'day', 'month', 'part', precisão desconhecida e data
     nula; filtrar_registros() "envolve pelo menos um de", filtro vazio
     desligado, período com as duas pontas incluídas, lista nula sem erro;
     ler() devolve os marts pedidos e deixa fora o que não existe; cada
     função de gráfico devolve uma figura com tantos pontos quantas linhas
     tem o DataFrame inventado (regioes sem a linha GLOBAL; fontes no
     máximo 10); so_incidentes plota a coluna _so_incidentes; o 02 anota
     "parcial" só no mês marcado; legenda_global() traz o número do GLOBAL
     e devolve None sem ele.
   Caminho de erro que encerra com sys.exit: pytest.raises(SystemExit), e
   o assert confere code == 1.

5. ESTILO
   pytest puro: funções test_* com assert. Fixtures, só tmp_path,
   monkeypatch e capsys (a saída na tela é o instrumento de conferência das
   etapas 1 a 3; o teste da tela lê com capsys). DuckDB de verdade, nunca
   mock do banco. Função auxiliar de montagem no próprio arquivo de teste
   é permitida; conftest.py, não.
   O nome do teste é a frase que ele prova:
     test_dano_nulo_em_policy_nao_se_aplica
   Proibido: teste sem assert, skip, xfail, try/except em volta do assert,
   pytest.approx em contagem. Motivo: cada um sobe o coverage sem provar
   nada.

6. NÃO ALTERE O CÓDIGO DO PROJETO
   Nenhum arquivo muda fora de test/ e do pyproject.toml. Se uma parte só
   for testável mudando o código, não mude: liste na entrega, com o motivo.

CRITÉRIOS DE ACEITE
- uv run pytest --cov termina sem falha, com TOTAL de 60% ou mais.
- Com incidentes.duckdb e data/raw/ renomeados, o resultado é o mesmo, e
  nenhum incidentes.duckdb novo aparece na raiz.
- Rodar duas vezes seguidas imprime a mesma coisa, fora o tempo de
  execução.
- Uma busca pelas palavras inteiras 395 e 724 dentro de test/ não encontra
  nada.
- Nenhum arquivo fora de test/ e do pyproject.toml tem data de modificação
  nova, fora os gerados pelo próprio pytest (.pytest_cache, .coverage,
  __pycache__). O projeto não está em git; a conferência é pela data.

ENTREGA
1. Os arquivos de teste.
2. A saída de uv run pytest --cov, com a tabela por arquivo.
3. As linhas que ficaram sem teste (coluna Missing) e por que não valeram
   o esforço agora.
4. Uma lista final do que você assumiu e que não estava na spec.
