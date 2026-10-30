"""Testes de pipeline/marts.py: itens 1 a 4 da docstring do módulo.

Os .sql daqui são escritos pelo teste; os de sql/marts/ estão em
test_sql_marts.py.
"""

import duckdb
import pytest

from pipeline import db, marts


def _preparar(tmp_path, monkeypatch, arquivos, faltando=()):
    banco = tmp_path / "incidentes.duckdb"
    pasta = tmp_path / "marts"
    pasta.mkdir()
    monkeypatch.setattr(db, "_BANCO", banco)
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta)
    con = duckdb.connect(banco)
    con.execute("CREATE SCHEMA refined")
    # As seis tabelas só precisam existir: os .sql do teste não as leem.
    for tabela in marts.TABELAS_REFINED:
        if tabela not in faltando:
            con.execute(f"CREATE TABLE refined.{tabela} AS SELECT 1 AS a")
    con.close()
    _escrever(pasta, arquivos)
    return banco, pasta


def _escrever(pasta, arquivos):
    for nome, sql in arquivos.items():
        (pasta / nome).write_text(sql, encoding="utf-8")


def _marts(banco):
    con = duckdb.connect(banco)
    try:
        nomes = [
            t
            for (t,) in con.execute(
                "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'mart'"
            ).fetchall()
        ]
        return {n: con.execute(f"SELECT count(*) FROM mart.{n}").fetchall()[0][0] for n in nomes}
    finally:
        con.close()


def _encerra():
    with pytest.raises(SystemExit) as saida:
        marts.main()
    assert saida.value.code == 1


def test_arquivo_vira_tabela_sem_prefixo_e_sem_ponto_e_virgula(tmp_path, monkeypatch):
    # Ponto e vírgula e linhas em branco no final: tirados antes do CREATE.
    banco, _ = _preparar(tmp_path, monkeypatch, {"00_teste.sql": "SELECT 1 AS x;\n\n"})

    marts.main()

    assert _marts(banco) == {"teste": 1}


def test_arquivo_sem_prefixo_para_antes_de_executar_qualquer_sql(tmp_path, monkeypatch, capsys):
    # 01_bom.sql é válido e vem antes: mesmo assim não pode ser executado.
    banco, _ = _preparar(
        tmp_path, monkeypatch, {"01_bom.sql": "SELECT 1 AS x", "teste.sql": "SELECT 1 AS x"}
    )

    _encerra()

    assert "teste.sql" in capsys.readouterr().out
    assert _marts(banco) == {}


def test_dois_arquivos_com_o_mesmo_nome_de_tabela_param(tmp_path, monkeypatch, capsys):
    banco, _ = _preparar(
        tmp_path, monkeypatch, {"01_x.sql": "SELECT 1 AS x", "02_x.sql": "SELECT 2 AS x"}
    )

    _encerra()

    assert "mart.x: 01_x.sql, 02_x.sql" in capsys.readouterr().out
    assert _marts(banco) == {}


def test_pasta_sem_sql_para(tmp_path, monkeypatch, capsys):
    _preparar(tmp_path, monkeypatch, {})

    _encerra()

    assert "Nenhum arquivo .sql" in capsys.readouterr().out


def test_tabela_de_refined_faltando_para(tmp_path, monkeypatch, capsys):
    banco, _ = _preparar(tmp_path, monkeypatch, {"01_a.sql": "SELECT 1 AS x"}, faltando=("fontes",))

    _encerra()

    tela = capsys.readouterr().out
    assert "refined.fontes" in tela
    assert "uv run python -m pipeline.transformacao" in tela
    assert _marts(banco) == {}


def test_sql_com_erro_encerra_e_deixa_mart_como_estava(tmp_path, monkeypatch, capsys):
    banco, pasta = _preparar(tmp_path, monkeypatch, {"01_a.sql": "SELECT 1 AS x"})
    marts.main()
    capsys.readouterr()
    # 02 tem erro de sintaxe; 03 é válido e não pode chegar a rodar.
    _escrever(pasta, {"02_b.sql": "SELEC 1", "03_c.sql": "SELECT 1 AS y"})

    _encerra()

    assert "Falhou: 02_b.sql" in capsys.readouterr().out
    assert _marts(banco) == {"a": 1}


def test_mart_vazio_encerra_e_deixa_mart_como_estava(tmp_path, monkeypatch, capsys):
    banco, pasta = _preparar(tmp_path, monkeypatch, {"01_a.sql": "SELECT 1 AS x"})
    marts.main()
    capsys.readouterr()
    # Zero linhas: o JOIN que não casou.
    _escrever(pasta, {"02_vazio.sql": "SELECT 1 AS x WHERE false"})

    _encerra()

    assert "Mart vazio: mart.vazio" in capsys.readouterr().out
    assert _marts(banco) == {"a": 1}


def test_arquivo_apagado_faz_o_mart_sumir_na_execucao_seguinte(tmp_path, monkeypatch):
    banco, pasta = _preparar(
        tmp_path, monkeypatch, {"01_a.sql": "SELECT 1 AS x", "02_b.sql": "SELECT 1 AS x"}
    )
    marts.main()

    (pasta / "02_b.sql").unlink()
    marts.main()

    assert _marts(banco) == {"a": 1}


def test_marts_rodam_em_ordem_alfabetica(tmp_path, monkeypatch, capsys):
    # Escritos fora de ordem: a tela segue o nome do arquivo.
    _preparar(tmp_path, monkeypatch, {"02_b.sql": "SELECT 1 AS x", "01_a.sql": "SELECT 1 AS x"})

    marts.main()

    linhas = capsys.readouterr().out.splitlines()
    assert [linha.split()[1] for linha in linhas[:2]] == ["mart.a", "mart.b"]


def test_tela_mostra_contagem_com_milhar_com_ponto_e_linha_final(tmp_path, monkeypatch, capsys):
    # 1.500 linhas: só para a contagem passar do milhar.
    _preparar(tmp_path, monkeypatch, {"01_grande.sql": "SELECT * FROM range(1500)"})

    marts.main()

    assert capsys.readouterr().out.splitlines() == [
        f"✓ mart.{'grande':<26} 1.500 linhas",
        "1 marts, 1.500 linhas",
    ]


def test_nenhuma_view_no_schema_mart(tmp_path, monkeypatch):
    banco, _ = _preparar(tmp_path, monkeypatch, {"01_a.sql": "SELECT 1 AS x"})

    marts.main()

    con = duckdb.connect(banco)
    views = con.execute("SELECT count(*) FROM duckdb_views() WHERE schema_name = 'mart'").fetchall()
    con.close()
    assert views == [(0,)]
