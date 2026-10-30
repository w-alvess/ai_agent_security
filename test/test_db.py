"""Testes de pipeline/db.py: regras D1 a D4 da docstring do módulo."""

from pathlib import Path

import duckdb
import pandas as pd

from pipeline import db


def test_conectar_cria_o_banco_em_banco_e_nao_na_pasta_corrente(tmp_path, monkeypatch):
    caminho = tmp_path / "raiz" / "incidentes.duckdb"
    caminho.parent.mkdir()
    corrente = tmp_path / "outra_pasta"
    corrente.mkdir()
    monkeypatch.setattr(db, "_BANCO", caminho)
    monkeypatch.chdir(corrente)

    con = db.conectar()
    con.close()

    assert caminho.is_file()
    assert not (corrente / "incidentes.duckdb").exists()


def test_pasta_raw_sai_da_localizacao_do_modulo_e_nao_da_pasta_corrente(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    esperado = Path(db.__file__).resolve().parent.parent / "data" / "raw"

    assert db.PASTA_RAW == esperado
    assert tmp_path not in db.PASTA_RAW.parents


def test_criar_schema_duas_vezes_nao_falha(tmp_path):
    con = duckdb.connect(tmp_path / "t.duckdb")
    db.criar_schema(con, "raw")
    db.criar_schema(con, "raw")

    schemas = con.execute(
        "SELECT count(*) FROM duckdb_schemas() WHERE schema_name = 'raw'"
    ).fetchall()[0][0]
    con.close()

    assert schemas == 1


def test_gravar_tres_linhas_devolve_tres_e_de_novo_tres(tmp_path):
    con = duckdb.connect(tmp_path / "t.duckdb")
    db.criar_schema(con, "raw")
    # Três linhas quaisquer: a contagem tem que ser a do banco.
    df = pd.DataFrame({"id": ["a", "b", "c"]})

    primeira = db.gravar(con, df, "raw", "t")
    # Recriar, não acrescentar: a segunda gravação continua com três.
    segunda = db.gravar(con, df, "raw", "t")
    no_banco = con.execute("SELECT count(*) FROM raw.t").fetchall()[0][0]
    con.close()

    assert (primeira, segunda, no_banco) == (3, 3, 3)


def test_gravar_mantem_str_como_varchar_e_nulo_como_null(tmp_path):
    con = duckdb.connect(tmp_path / "t.duckdb")
    db.criar_schema(con, "raw")
    # "2024" parece número e não pode virar número; None tem que ficar NULL.
    df = pd.DataFrame({"ano": ["2024", None, "2025"]}, dtype=str)

    db.gravar(con, df, "raw", "t")
    tipo = con.execute(
        "SELECT data_type FROM duckdb_columns() WHERE table_name = 't' AND column_name = 'ano'"
    ).fetchall()[0][0]
    nulos = con.execute("SELECT count(*) FROM raw.t WHERE ano IS NULL").fetchall()[0][0]
    con.close()

    assert tipo == "VARCHAR"
    assert nulos == 1


def test_gravar_nao_deixa_view_para_tras(tmp_path):
    con = duckdb.connect(tmp_path / "t.duckdb")
    db.criar_schema(con, "raw")

    db.gravar(con, pd.DataFrame({"id": ["a"]}), "raw", "t")
    views = con.execute(
        "SELECT count(*) FROM duckdb_views() WHERE NOT internal"
    ).fetchall()[0][0]
    con.close()

    assert views == 0
