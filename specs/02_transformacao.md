CONTEXTO
Estou construindo um pipeline de dados em Python sobre o dataset público
"AI Agent Security and Real-World Incidents 2024-26" do Kaggle. A etapa 1
(ingestão) já copiou os CSVs para o schema raw sem decidir nada. Esta é a
etapa 2: a passagem de raw para refined, onde as decisões acontecem e ficam
registradas. Trabalho com spec-driven development: a spec abaixo é a fonte
da verdade e o código é consequência dela. Não acrescente requisito que não
esteja escrito aqui. Se algo estiver ambíguo, pergunte antes de escrever
código.

STACK
- Python 3.14, dependências gerenciadas com uv
- DuckDB 2.x, arquivo incidentes.duckdb na raiz do projeto
- Nenhum orquestrador. Script executável pela linha de comando.

O QUE JÁ EXISTE (use, não reimplemente)
pipeline/db.py expõe:
  conectar()                 abre o incidentes.duckdb, criando se faltar
  criar_schema(con, nome)    CREATE SCHEMA IF NOT EXISTS
  (gravar() não serve aqui: grava DataFrame, e esta etapa não traz dado
   para a memória — ver item 3.)
O schema raw, criado pela etapa 1: quatro tabelas, todas as colunas
VARCHAR, campo vazio como NULL.

ARTEFATO A PRODUZIR
pipeline/transformacao.py, executável com:
  uv run python -m pipeline.transformacao

SPEC

1. ESCOPO
   Lê de raw, escreve no schema refined. Nunca escreve em raw.
   Entram três tabelas: incidentes_completo, tipos_ataque, tendencia_mensal.
   Saem seis: incidentes, tipos_ataque e tendencia_mensal (uma para uma) e
   as três tabelas-ponte do item 2b, derivadas de refined.incidentes.
   Fica de fora:
     raw.incidentes  é uma projeção de incidentes_completo: os mesmos 395
                     ids e as mesmas 12 colunas comuns, idênticas. Tudo o
                     que ela tem a mais é pior: trocou os 87 nulos de
                     real_harm por False (um "não houve dano" que ninguém
                     afirmou), source_count é 1 em todas as linhas mesmo
                     com incidentes de até 8 fontes, primary_source_url é a
                     lista inteira e não a primeira fonte, year e
                     attack_type_name se derivam de date e de tipos_ataque.
                     Ela continua em raw; só não vira refined.

2. NOMES
   Colunas renomeadas para português, snake_case, com o mapa abaixo,
   completo e literal. Nenhuma coluna fora do mapa; nenhuma descartada —
   inclusive as traduções e os caminhos, que entram mesmo sem uso previsto.
   Motivo: é o vocabulário que vou digitar de memória nos JOINs do mart.

   incidentes  (de raw.incidentes_completo)
     id -> incidente_id                    date -> data
     date_end -> data_fim                  date_precision -> precisao_data
     month -> mes
     title -> titulo                       title_zh -> titulo_zh
     title_ja -> titulo_ja                 title_ko -> titulo_ko
     title_de -> titulo_de                 title_fr -> titulo_fr
     title_es -> titulo_es
     kind -> natureza                      type -> codigos_ataque
     severity -> severidade                confidence -> confianca
     real_harm -> dano_real                ai_involvement -> envolvimento_ia
     region -> regioes                     disputed -> contestado
     landmark -> marco
     summary -> resumo                     summary_zh -> resumo_zh
     summary_ja -> resumo_ja               summary_ko -> resumo_ko
     summary_de -> resumo_de               summary_fr -> resumo_fr
     summary_es -> resumo_es
     sources -> urls_fontes
     path -> caminho                       path_zh -> caminho_zh
   tipos_ataque
     type_code -> codigo                   type_name -> nome
     incident_count -> qtd_incidentes      description -> descricao
   tendencia_mensal
     month -> mes                          total_incidents -> total_incidentes
     critical_incidents -> incidentes_criticos
     high_severity_incidents -> incidentes_alta
     medium_severity_incidents -> incidentes_media
     real_harm_confirmed -> dano_real_confirmado

2b. TABELAS-PONTE
   Três colunas de refined.incidentes guardam vários valores separados por
   ';': codigos_ataque (até 3), regioes (até 2) e urls_fontes (até 8).
   Cada uma vira uma tabela com uma linha por incidente × valor:
     incidente_tipos    (incidente_id, posicao, codigo_ataque)
     incidente_regioes  (incidente_id, posicao, regiao)
     fontes             (incidente_id, posicao, url)
   posicao é a ordem do valor na string original, começando em 1.
   A coluna original continua em refined.incidentes, inalterada.
   Motivo: 120 incidentes têm codigos_ataque como 'IPI;EXFIL', que não faz
   JOIN com tipos_ataque.codigo; sem a ponte, todo mart que agrupa por tipo
   reinventa o split. posicao existe porque a ordem pode significar
   prioridade e, sem ela, o split não teria volta. A string original fica
   porque refined não apaga o dado que recebeu.
   Pedaço vazio (ex.: 'IPI;;EXFIL' ou ';' no fim) é conversão que falha:
   para, como no item 4. Nada de trim, nada de mudar maiúsculas.

3. TIPOS
   Datas: DATE, formato declarado '%Y-%m-%d' (data, data_fim).
     precisao_data fica ao lado, como veio. Motivo: 47 incidentes com
     precisão 'month' estão no dia 01 e 6 com 'part' no dia 15; o dia
     deles é inventado. Apagar o dia seria apagar o mês junto; quem lê
     data decide quanto confiar nela olhando precisao_data.
   mes (nas duas tabelas): continua VARCHAR 'AAAA-MM'. Motivo: é um
     período, não um dia; como DATE ganharia um dia 01 que não existe. É
     também a chave de JOIN entre incidentes e tendencia_mensal.
   Booleanos (dano_real, contestado, marco): BOOLEAN. Só 'true' vira true
     e só 'false' vira false; qualquer outro valor é conversão que falha.
     Motivo: CAST(... AS BOOLEAN) do DuckDB aceita calado 'yes', 'T' e
     '1'. Um valor fora do vocabulário é sinal de que a fonte mudou, e
     isso tem que aparecer, não ser absorvido.
   Contagens (qtd_incidentes, total_incidentes, incidentes_criticos,
     incidentes_alta, incidentes_media, dano_real_confirmado, posicao):
     INTEGER.
   Todo o resto continua VARCHAR — inclusive severidade, confianca,
     natureza e envolvimento_ia, sem mudar maiúsculas. Motivo: são
     rótulos; normalizar 'A' para 'a' é decidir que são iguais, e o dado
     não disse isso.
   A conversão é feita em SQL pelo DuckDB (strptime, CAST, CASE), disparada
   pelo Python. Motivo: o dado já está no banco; não há por que trazê-lo
   para a memória só para converter tipo.

4. CONVERSÃO QUE FALHA
   Para tudo. Use strptime e CAST, que estouram, e nunca try_strptime,
   TRY_CAST ou errors="coerce", que transformam falha em nulo.
   Ao falhar: diga tabela, coluna e um exemplo do valor que não converteu,
   e encerre com sys.exit(1), sem ter gravado nenhuma tabela em refined.
   Motivo: um nulo fabricado pela conversão fica indistinguível de um nulo
   verdadeiro do dado, para sempre.

5. DUPLICATAS
   Chave de cada tabela:
     incidentes (incidente_id)        tipos_ataque (codigo)
     tendencia_mensal (mes)
     pontes (incidente_id, posicao) — única por construção.
   Linha inteira repetida: mantém uma, e conta quantas saíram.
   Chave repetida com conteúdo diferente: para, mostra a chave e as linhas
   conflitantes, sys.exit(1), sem ter gravado nada em refined. Não escolhe
   uma por conta própria.
   Motivo: escolher em silêncio é decidir sem dizer que decidiu.

6. NULOS
   Nenhuma linha é apagada por ter nulo. Nenhum nulo é preenchido.
   Motivo: data_fim nula é a regra (381 de 395): o incidente aconteceu num
   dia, não num intervalo. dano_real nulo (87) são exatamente os registros
   de natureza policy (72) e report (15): uma lei ou um relatório não têm
   dano, a pergunta não se aplica. Isso é diferente de false — exatamente
   a diferença que raw.incidentes apagou.
   Anomalias de negócio também ficam (ex.: 15 incidentes contestados,
   'GLOBAL' combinado com país em regioes). refined não corrige fato; quem
   decide o que fazer com ele é a pergunta que o mart responde.

7. SAÍDA NA TELA
   Uma linha por tabela, na ordem do item 1, no formato:
     refined.incidentes          395 -> 395 linhas  (0 duplicatas)
   Nas pontes, a entrada é refined.incidentes e não há duplicatas:
     refined.fontes              395 -> 797 linhas
   Abaixo dela, indentadas, as colunas com nulo e a contagem:
       nulos mantidos: data_fim 381, dano_real 87
   As contagens vêm do banco, milhar separado por ponto. Linha final com o
   total de linhas gravadas. stdout reconfigurado para utf-8.

REEXECUÇÃO
   CREATE OR REPLACE TABLE, nunca acrescenta. Rodar dez vezes = rodar uma.
   As seis tabelas são gravadas numa única transação: ou saem todas, ou
   refined fica como estava.

ERRO
   Antes de transformar, verifica se as três tabelas de entrada existem em
   raw. Faltando qualquer uma: lista quais, diz para rodar
   "uv run python -m pipeline.ingestao" e encerra com sys.exit(1).

CRITÉRIOS DE ACEITE
- Seis tabelas em refined: incidentes 395, tipos_ataque 12,
  tendencia_mensal 23, incidente_tipos 511, incidente_regioes 409,
  fontes 797. Total: 2.147. Com este dado, 0 duplicatas.
- DESCRIBE refined.incidentes mostra DATE em data e data_fim, BOOLEAN em
  dano_real, contestado e marco, e 31 colunas.
- Nulos depois = nulos antes: data_fim 381, dano_real 87; nenhuma outra
  coluna com nulo. dano_real: 141 true, 167 false, 87 nulos.
- Todo incidente_tipos.codigo_ataque existe em tipos_ataque.codigo.
- SELECT count(DISTINCT url) FROM refined.fontes = 724 (as mesmas 724 de
  sources_bibliography.txt).
- string_agg(codigo_ataque, ';' ORDER BY posicao) por incidente devolve
  exatamente refined.incidentes.codigos_ataque (idem regioes e fontes).
- count(*) de refined.incidentes por mes bate com
  tendencia_mensal.total_incidentes nos 23 meses.
- Trocar um 'true' de raw.incidentes_completo.disputed por 'yes' faz o
  script parar dizendo tabela, coluna e o valor, sem gravar nada.
- Rodar duas vezes seguidas imprime exatamente a mesma coisa.

ENTREGA, nesta ordem
1. A spec como docstring no topo do arquivo, dizendo por que cada regra
   existe — não só o que ela manda fazer.
2. O código, com comentários apenas onde a decisão não é óbvia pelo código.
3. Uma lista final do que você assumiu e que não estava na spec. Se a lista
   não estiver vazia, é a minha spec que precisa melhorar.
