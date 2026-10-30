CONTEXTO
Estou construindo um pipeline de dados em Python sobre o dataset público
"AI Agent Security and Real-World Incidents 2024-26" do Kaggle
(muhammadahmerkhan/ai-agent-security-and-real-world-incidents-2024-26):
incidentes de segurança envolvendo agentes de IA, com taxonomia de ataques,
série mensal e lista de fontes. Trabalho com spec-driven development: a spec
abaixo é a fonte da verdade e o código é consequência dela. Não acrescente
requisito que não esteja escrito aqui. Se algo estiver ambíguo, pergunte
antes de escrever código.

STACK
- Python 3.14, dependências gerenciadas com uv
- pandas para ler os arquivos
- DuckDB 2.x como banco, arquivo incidentes.duckdb na raiz do projeto
- Nenhum orquestrador. Script executável pela linha de comando.

O QUE JÁ EXISTE
- data/raw/ com os arquivos do dataset (quatro .csv e um .txt; só os
  quatro .csv são ingeridos, ver item 1 da ingestão)
- scripts/download_data.py, que baixa o dataset do Kaggle para data/raw/
- pyproject.toml e .gitignore (data/raw/ e o incidentes.duckdb ficam fora
  do git: os dois são recriados pelos scripts)
Nenhum código de pipeline ainda.

ARTEFATOS A PRODUZIR, nesta ordem
1. pipeline/db.py, o módulo de conexão que todas as etapas do pipeline vão
   importar (spec própria logo abaixo; é a primeira coisa a existir)
2. pipeline/ingestao.py, executável com:
     uv run python -m pipeline.ingestao
3. ui.py, na raiz do projeto, executável com:
     uv run python ui.py
   (spec própria no fim deste prompt; ui.py e ingestao.py não se importam)

SPEC DO pipeline/db.py (primeiro artefato)
Expõe exatamente isto, com estes nomes:
  PASTA_RAW                          Path da pasta data/raw/ com os arquivos do dataset
  conectar()                         abre o incidentes.duckdb, criando se faltar
  criar_schema(con, nome)            CREATE SCHEMA IF NOT EXISTS
  gravar(con, df, schema, tabela)    grava e devolve a contagem lida do banco

D1. CAMINHOS
    PASTA_RAW e o incidentes.duckdb são resolvidos a partir da localização
    do próprio db.py (a pasta acima de pipeline/), nunca do diretório
    corrente. PASTA_RAW = <raiz>/data/raw.
    Motivo: rodar o script de outra pasta não pode criar um
    incidentes.duckdb vazio no lugar errado, que parece ingestão quebrada.
D2. TRÊS FUNÇÕES E UMA CONSTANTE, NADA MAIS
    db.py não lê CSV, não conhece nome de tabela, não imprime nada
    e não converte tipo. Quem decide tudo isso é cada etapa.
    Motivo: as etapas seguintes importam este arquivo. Regra de negócio
    escondida aqui vale para todas as etapas sem aparecer em nenhuma spec.
D3. gravar
    Recria a tabela (CREATE OR REPLACE TABLE schema.tabela) com as colunas
    e os tipos do DataFrame, sem alterar nada: coluna str vira VARCHAR,
    nulo continua NULL. Não deixa view ou tabela temporária para trás.
    Devolve SELECT count(*) da tabela recém-gravada, lido do banco.
    Motivo: a contagem que aparece na tela tem que ser a do que foi
    gravado, não a do que estava na memória.
D4. CONEXÃO
    conectar() devolve a conexão aberta; quem chama é quem fecha.
    db.py não guarda conexão global.

CRITÉRIOS DE ACEITE (db.py)
- Importar pipeline.db não abre banco nem cria arquivo nenhum.
- conectar() chamado de dentro de outra pasta cria o incidentes.duckdb na
  raiz do projeto, e não na pasta corrente.
- gravar() com um DataFrame de 3 linhas devolve 3, e rodar duas vezes
  continua devolvendo 3.

SPEC DA INGESTÃO (segundo artefato)

1. ESCOPO E NOMES
   Schema de destino: raw
   Mapa arquivo -> tabela, completo e literal:
     ai_agent_incidents_clean.csv   -> incidentes
     ai_agent_incidents_full.csv    -> incidentes_completo
     taxonomy_attack_types.csv      -> tipos_ataque
     monthly_incident_trends.csv    -> tendencia_mensal
   Os nomes das tabelas vão para o português porque é o vocabulário que vou
   digitar de memória num JOIN nas próximas etapas. Os nomes das colunas
   ficam como vieram (ver item 2).
   sources_bibliography.txt fica em data/raw/, mas NÃO é ingerido, nem
   verificado no item 7.
   Motivo: as 724 URLs dele são exatamente as URLs da coluna sources de
   ai_agent_incidents_full.csv, sem repetição e sem dizer a que incidente
   cada uma pertence. Ingerir esse arquivo traria um dado redundante e menos
   informativo, e exigiria uma regra de leitura só para ele (não tem
   cabeçalho). Se o dashboard precisar de fontes, a tabela sai da coluna
   sources na etapa refined, mantendo a ligação com o incidente.

2. PROIBIÇÕES (a regra central desta etapa)
   Nenhuma conversão de tipo. Nenhuma linha descartada ou deduplicada.
   Nenhum nome de coluna alterado. Nenhum valor corrigido, preenchido ou
   normalizado. Data continua texto, "True"/"False" continuam texto, nulo
   continua nulo. As colunas traduzidas (title_zh, summary_ja etc.) entram
   como estão, mesmo que eu não vá usá-las.
   incidentes e incidentes_completo entram as duas, mesmo descrevendo os
   mesmos incidentes: escolher uma, ou juntar as duas, é decisão da etapa
   refined, não da ingestão.
   Motivo: a fronteira entre "o dado que chegou" e "o dado que eu decidi"
   precisa existir em algum lugar, e esse lugar é a passagem de raw para
   refined, na etapa 2. Se a correção acontecer aqui, a fronteira some.

3. REEXECUÇÃO
   Rodar dez vezes tem que dar o mesmo resultado que rodar uma: a tabela é
   recriada (CREATE OR REPLACE), nunca acrescentada. É o que me deixa errar
   sem medo.

4. LEITURA DOS ARQUIVOS
   encoding declarado como utf-8, nunca adivinhado. Os arquivos trazem
   texto em chinês, japonês e coreano; adivinhar encoding aqui corrompe
   essas colunas sem erro.
   Campo vazio continua virando nulo; não transforme em string vazia.
   Só campo vazio vira nulo: texto como "NA", "None" ou "null" continua
   texto (keep_default_na=False, na_values=[""]).
   Motivo: o padrão do pandas transforma "NA" em nulo, e "NA" é também a
   sigla de América do Norte numa coluna de região.

5. TIPAGEM
   Toda coluna entra como texto (dtype=str), inferência desligada.
   Motivo: inferência lê year, month e incident_count como número, e
   "2024-12" pode virar data ou ser rejeitado conforme a versão. A
   conversão acontece na etapa 2, onde é uma decisão registrada.

6. SAÍDA NA TELA
   Uma linha por tabela, com nome qualificado e contagem de linhas vinda do
   banco (não do DataFrame), milhar separado por ponto, na ordem do mapa do
   item 1.
   Uma linha final com o total.
   Essa saída é meu único instrumento de conferência nesta etapa.
   O stdout precisa ser reconfigurado para utf-8: rodo no Prompt de Comando
   do Windows, onde acento sai embaralhado por padrão.

7. ERRO
   Antes de abrir o banco, verifique se os quatro .csv do mapa existem.
   Faltando qualquer um: liste os que faltam, diga em que pasta procurou,
   diga que eles são baixados com uv run python scripts/download_data.py e
   encerre com sys.exit(1). Não ingira parcialmente.
   Motivo: ingerir três de quatro tabelas em silêncio produz um dashboard
   errado que parece certo.

CRITÉRIOS DE ACEITE (ingestão)
- A execução imprime quatro linhas e um total de 825 registros
  (395 + 395 + 12 + 23).
- Rodar duas vezes seguidas imprime exatamente a mesma coisa.
- SELECT * FROM raw.incidentes devolve todas as 17 colunas como VARCHAR, e
  raw.incidentes_completo todas as 31.
- Em raw.incidentes_completo, date_end tem 381 NULL e real_harm tem 87
  NULL, e nenhuma das duas tem string vazia.
- Nenhuma tabela raw.fontes existe; remover sources_bibliography.txt da
  pasta não muda nada na execução.
- Remover um arquivo da pasta faz o script parar antes de gravar qualquer
  tabela.
- O script termina sozinho e devolve o terminal: nenhum processo fica de pé.

SPEC DO ui.py (terceiro artefato)
Quero explorar o banco pelo navegador, em vez de ler tabela no terminal.

U1. O QUE FAZ
    Abre o incidentes.duckdb da raiz do projeto, instala e carrega a
    extensão `ui` do DuckDB (INSTALL ui; LOAD ui;) e chama CALL start_ui(),
    que sobe o servidor em http://localhost:4213 e abre o navegador.
U2. FICA DE PÉ ATÉ CTRL+C
    A extensão serve enquanto a conexão estiver viva. O script mantém o
    processo rodando, imprime a URL e a instrução "Ctrl+C para encerrar", e
    no Ctrl+C fecha a conexão e sai limpo, sem traceback.
    Motivo: o arquivo .duckdb aceita um único processo escrevendo. Com o
    ui.py de pé, a ingestão falha com um IOException do DuckDB. No Windows
    a mensagem é "Cannot open file ... O arquivo já está sendo usado por
    outro processo", seguida de "File is already open in ... (PID n)", que
    diz qual processo segura o arquivo; em Linux/macOS é "Could not set
    lock on file". Saber exatamente como desligar o servidor faz parte da
    ferramenta.
U3. NÃO CRIA BANCO
    Se incidentes.duckdb não existir, diga que é preciso rodar a ingestão
    antes e encerre com sys.exit(1). Por isso NÃO use conectar() de
    pipeline/db.py, que cria o arquivo quando ele falta: um banco vazio
    aberto no navegador parece ingestão quebrada.
U4. SEPARAÇÃO
    ui.py não importa pipeline/ingestao.py, e a ingestão não importa ui.py:
    a ingestão não sobe servidor, não abre navegador e não depende da
    extensão ui para rodar.
U5. SAÍDA NA TELA
    Mesma regra do item 6: stdout reconfigurado para utf-8.

CRITÉRIOS DE ACEITE (ui.py)
- uv run python ui.py abre o navegador em localhost:4213 e o schema raw
  aparece com as quatro tabelas.
- Ctrl+C devolve o terminal sem traceback, e logo depois a ingestão roda
  sem erro de lock.
- Renomear incidentes.duckdb faz o ui.py parar com a mensagem, sem criar
  arquivo novo.

ENTREGA, nesta ordem, para cada um dos três arquivos
1. A spec como docstring no topo do arquivo, dizendo por que cada regra
   existe — não só o que ela manda fazer.
2. O código, com comentários apenas onde a decisão não é óbvia pelo código.
3. Uma lista final do que você assumiu e que não estava na spec. Se a lista
   não estiver vazia, é a minha spec que precisa melhorar.
