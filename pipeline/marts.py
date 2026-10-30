"""Marts: grava cada sql/marts/NN_nome.sql como tabela mart.nome.

Executar com:  uv run python -m pipeline.marts

1. ESCOPO
   Lê de refined, escreve em mart, nunca escreve em raw nem em refined.
   O schema mart é apagado e recriado a cada execução (DROP SCHEMA IF EXISTS
   mart CASCADE). Por quê: um mart cujo arquivo foi apagado não pode
   continuar existindo no banco.

2. UM ARQUIVO, UMA TABELA
   Todos os sql/marts/*.sql, em ordem alfabética. Tabela = nome do arquivo
   sem extensão e sem o prefixo NN_ (01_tipos_ataque.sql -> mart.tipos_ataque).
   Executa CREATE TABLE mart.<nome> AS <conteúdo>, tirando só espaços e um
   ponto e vírgula do final. O Python não altera, não monta e não completa
   a SQL. Por quê: a regra de negócio mora inteira no arquivo .sql, onde a
   spec de cada mart a documenta.

3. SAÍDA NA TELA
   Uma linha por mart com a contagem lida do banco, milhar com ponto, e uma
   linha final com o número de marts e o total. stdout em utf-8. Por quê:
   é o instrumento de conferência desta etapa, e no Prompt de Comando do
   Windows acento sai embaralhado por padrão.

4. ERRO
   Antes de tudo, as seis tabelas de refined têm que existir; faltando
   alguma, lista quais e manda rodar a transformação.
   Pasta sem .sql, arquivo sem prefixo NN_ ou dois arquivos com o mesmo nome
   de tabela: lista e para antes de executar qualquer SQL. Por quê: errar
   antes de começar não deixa nada pela metade.
   .sql que falha: nome do arquivo e mensagem do DuckDB, não executa os
   seguintes. Mart com zero linhas: para. Por quê: mart vazio é quase sempre
   um JOIN que não casou, e um dashboard vazio parece um problema que sumiu.
   Tudo numa transação só: qualquer falha devolve o schema mart ao estado da
   última execução que deu certo. Por quê: um schema pela metade quebra o
   dashboard sem avisar.
   Toda falha encerra com sys.exit(1).
"""

import re
import sys
from pathlib import Path

import duckdb

from pipeline.db import conectar, criar_schema

ORIGEM = "refined"
DESTINO = "mart"
PASTA_MARTS = Path(__file__).resolve().parent.parent / "sql" / "marts"

TABELAS_REFINED = [
    "incidentes",
    "tipos_ataque",
    "tendencia_mensal",
    "incidente_tipos",
    "incidente_regioes",
    "fontes",
]

PREFIXO = re.compile(r"^\d\d_(.+)$")


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _falhar(linhas: list[str]) -> None:
    for linha in linhas:
        print(linha)
    sys.exit(1)


def _verificar_refined(con: duckdb.DuckDBPyConnection) -> None:
    existentes = {
        nome
        for (nome,) in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name = ?", [ORIGEM]
        ).fetchall()
    }
    faltando = [t for t in TABELAS_REFINED if t not in existentes]
    if faltando:
        _falhar(
            [f"Tabelas faltando no schema {ORIGEM}:"]
            + [f"  {ORIGEM}.{nome}" for nome in faltando]
            + ["Rode a transformação antes: uv run python -m pipeline.transformacao"]
        )


def _listar_marts() -> list[tuple[Path, str]]:
    # sorted() sobre o nome: a ordem alfabética não pode depender do que o
    # sistema de arquivos devolve.
    arquivos = sorted(PASTA_MARTS.glob("*.sql"), key=lambda p: p.name)
    if not arquivos:
        _falhar([f"Nenhum arquivo .sql em {PASTA_MARTS}"])

    sem_prefixo = [a.name for a in arquivos if not PREFIXO.match(a.stem)]
    if sem_prefixo:
        _falhar(
            [f"Arquivos sem prefixo NN_ em {PASTA_MARTS}:"]
            + [f"  {nome}" for nome in sem_prefixo]
        )

    marts = [(a, PREFIXO.match(a.stem).group(1)) for a in arquivos]
    por_nome: dict[str, list[str]] = {}
    for arquivo, nome in marts:
        por_nome.setdefault(nome, []).append(arquivo.name)
    repetidos = {nome: arqs for nome, arqs in por_nome.items() if len(arqs) > 1}
    if repetidos:
        _falhar(
            ["Arquivos que dão o mesmo nome de tabela:"]
            + [f"  {DESTINO}.{nome}: {', '.join(arqs)}" for nome, arqs in repetidos.items()]
        )
    return marts


def _ler_sql(arquivo: Path) -> str:
    sql = arquivo.read_text(encoding="utf-8").rstrip()
    return sql.removesuffix(";")


def _gravar(
    con: duckdb.DuckDBPyConnection, marts: list[tuple[Path, str]]
) -> list[tuple[str, int]]:
    contagens = []
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f'DROP SCHEMA IF EXISTS "{DESTINO}" CASCADE')
        criar_schema(con, DESTINO)
        for arquivo, nome in marts:
            try:
                con.execute(f'CREATE TABLE "{DESTINO}"."{nome}" AS {_ler_sql(arquivo)}')
            except duckdb.Error as erro:
                con.execute("ROLLBACK")
                _falhar([f"Falhou: {arquivo.name}", f"  {erro}"])
            linhas = con.execute(f'SELECT count(*) FROM "{DESTINO}"."{nome}"').fetchall()[0][0]
            if linhas == 0:
                con.execute("ROLLBACK")
                _falhar([f"Mart vazio: {DESTINO}.{nome} ({arquivo.name})"])
            contagens.append((nome, linhas))
        con.execute("COMMIT")
    except SystemExit:
        raise
    except BaseException:
        con.execute("ROLLBACK")
        raise
    return contagens


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        _verificar_refined(con)
        marts = _listar_marts()
        contagens = _gravar(con, marts)
    finally:
        con.close()

    for nome, linhas in contagens:
        print(f"✓ {DESTINO}.{nome:<26} {_milhar(linhas):>5} linhas")
    total = sum(linhas for _, linhas in contagens)
    print(f"{len(contagens)} marts, {_milhar(total)} linhas")


if __name__ == "__main__":
    main()
