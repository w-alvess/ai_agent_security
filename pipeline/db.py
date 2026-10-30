"""Conexão com o incidentes.duckdb, compartilhada por todas as etapas.

Expõe exatamente isto:
  PASTA_RAW                          Path da pasta data/raw/ com os arquivos do dataset
  conectar()                         abre o incidentes.duckdb, criando se faltar
  criar_schema(con, nome)            CREATE SCHEMA IF NOT EXISTS
  gravar(con, df, schema, tabela)    grava e devolve a contagem lida do banco

D1. CAMINHOS
    PASTA_RAW e o incidentes.duckdb são resolvidos a partir da localização
    deste arquivo (a pasta acima de pipeline/), nunca do diretório corrente.
    Por quê: rodar o script de outra pasta não pode criar um
    incidentes.duckdb vazio no lugar errado, que parece ingestão quebrada.

D2. TRÊS FUNÇÕES E UMA CONSTANTE, NADA MAIS
    Este módulo não lê CSV, não conhece nome de tabela, não imprime nada e
    não converte tipo. Quem decide tudo isso é cada etapa.
    Por quê: as etapas seguintes importam este arquivo. Regra de negócio
    escondida aqui valeria para todas as etapas sem aparecer em nenhuma spec.

D3. gravar
    Recria a tabela (CREATE OR REPLACE TABLE schema.tabela) com as colunas e
    os tipos do DataFrame, sem alterar nada: coluna str vira VARCHAR, nulo
    continua NULL. Não deixa view ou tabela temporária para trás. Devolve
    SELECT count(*) da tabela recém-gravada, lido do banco.
    Por quê: a contagem que aparece na tela tem que ser a do que foi gravado,
    não a do que estava na memória.

D4. CONEXÃO
    conectar() devolve a conexão aberta; quem chama é quem fecha. Não há
    conexão global.
    Por quê: o arquivo .duckdb aceita um único processo escrevendo; uma
    conexão esquecida aberta segura o lock e trava a próxima execução.
"""

from pathlib import Path

import duckdb
import pandas as pd

_RAIZ = Path(__file__).resolve().parent.parent
_BANCO = _RAIZ / "incidentes.duckdb"

PASTA_RAW = _RAIZ / "data" / "raw"


def conectar() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(_BANCO)


def criar_schema(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{nome}"')


def gravar(
    con: duckdb.DuckDBPyConnection, df: pd.DataFrame, schema: str, tabela: str
) -> int:
    destino = f'"{schema}"."{tabela}"'
    # register cria uma view temporária na conexão; o finally garante que ela
    # some mesmo se o CREATE falhar.
    con.register("_df_gravar", df)
    try:
        con.execute(f"CREATE OR REPLACE TABLE {destino} AS SELECT * FROM _df_gravar")
    finally:
        con.unregister("_df_gravar")
    return con.execute(f"SELECT count(*) FROM {destino}").fetchall()[0][0]
