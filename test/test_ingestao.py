"""Testes de pipeline/ingestao.py: itens 1 a 7 da docstring do módulo."""

import duckdb
import pytest

from pipeline import db, ingestao

CSVS = {
    # Linha INC-2 repetida: a ingestão não deduplica.
    # region 'NA' (América do Norte) continua texto; region vazia vira NULL.
    "ai_agent_incidents_clean.csv": (
        "id,date,region\n"
        "INC-1,2025-01-10,NA\n"
        "INC-2,2025-02-01,\n"
        "INC-2,2025-02-01,\n"
    ),
    # Título em chinês chega intacto; real_harm 'True' continua texto.
    "ai_agent_incidents_full.csv": (
        "id,title_zh,real_harm\n"
        "INC-1,数据泄露,True\n"
        "INC-2,攻击,\n"
    ),
    # incident_count '2024' parece número e entra como texto.
    "taxonomy_attack_types.csv": "type_code,type_name,incident_count\nCRED,Credential,2024\n",
    "monthly_incident_trends.csv": "month,total_incidents\n2025-01,1\n",
}


def _preparar(tmp_path, monkeypatch, csvs=CSVS):
    pasta = tmp_path / "raw"
    pasta.mkdir()
    for nome, conteudo in csvs.items():
        (pasta / nome).write_text(conteudo, encoding="utf-8")
    banco = tmp_path / "incidentes.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta)
    monkeypatch.setattr(db, "_BANCO", banco)
    return banco, pasta


def _consultar(banco, sql):
    con = duckdb.connect(banco)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_cada_csv_vira_tabela_com_as_mesmas_linhas_inclusive_a_repetida(tmp_path, monkeypatch):
    banco, _ = _preparar(tmp_path, monkeypatch)

    ingestao.main()

    contagens = {
        t: _consultar(banco, f"SELECT count(*) FROM raw.{t}")[0][0]
        for t in ingestao.ARQUIVOS.values()
    }
    assert contagens == {
        "incidentes": 3,
        "incidentes_completo": 2,
        "tipos_ataque": 1,
        "tendencia_mensal": 1,
    }


def test_toda_coluna_entra_como_varchar(tmp_path, monkeypatch):
    banco, _ = _preparar(tmp_path, monkeypatch)

    ingestao.main()

    tipos = {
        tipo
        for (tipo,) in _consultar(
            banco, "SELECT DISTINCT data_type FROM duckdb_columns() WHERE schema_name = 'raw'"
        )
    }
    assert tipos == {"VARCHAR"}


def test_nomes_de_coluna_ficam_como_vieram(tmp_path, monkeypatch):
    banco, _ = _preparar(tmp_path, monkeypatch)

    ingestao.main()

    colunas = [
        c
        for (c,) in _consultar(
            banco,
            "SELECT column_name FROM duckdb_columns() WHERE schema_name = 'raw' "
            "AND table_name = 'tipos_ataque' ORDER BY column_index",
        )
    ]
    assert colunas == ["type_code", "type_name", "incident_count"]


def test_na_continua_texto_e_campo_vazio_vira_null(tmp_path, monkeypatch):
    banco, _ = _preparar(tmp_path, monkeypatch)

    ingestao.main()

    regioes = _consultar(banco, "SELECT region FROM raw.incidentes ORDER BY id, region")
    assert regioes == [("NA",), (None,), (None,)]


def test_texto_em_chines_chega_intacto(tmp_path, monkeypatch):
    banco, _ = _preparar(tmp_path, monkeypatch)

    ingestao.main()

    titulo = _consultar(banco, "SELECT title_zh FROM raw.incidentes_completo WHERE id = 'INC-1'")
    assert titulo == [("数据泄露",)]


def test_rodar_duas_vezes_da_as_mesmas_contagens_e_a_mesma_tela(tmp_path, monkeypatch, capsys):
    banco, _ = _preparar(tmp_path, monkeypatch)

    ingestao.main()
    primeira = capsys.readouterr().out
    ingestao.main()
    segunda = capsys.readouterr().out

    assert primeira == segunda
    assert _consultar(banco, "SELECT count(*) FROM raw.incidentes")[0][0] == 3


def test_sem_bibliografia_nada_muda_e_raw_fontes_nao_existe(tmp_path, monkeypatch):
    banco, pasta = _preparar(tmp_path, monkeypatch)
    # sources_bibliography.txt não foi escrito: a ingestão não depende dele.
    assert not (pasta / "sources_bibliography.txt").exists()

    ingestao.main()

    tabelas = {
        t for (t,) in _consultar(banco, "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'raw'")
    }
    assert tabelas == set(ingestao.ARQUIVOS.values())


def test_arquivo_faltando_encerra_antes_de_criar_o_banco(tmp_path, monkeypatch, capsys):
    sem_mensal = {k: v for k, v in CSVS.items() if k != "monthly_incident_trends.csv"}
    banco, _ = _preparar(tmp_path, monkeypatch, sem_mensal)

    with pytest.raises(SystemExit) as saida:
        ingestao.main()

    assert saida.value.code == 1
    assert not banco.exists()
    tela = capsys.readouterr().out
    assert "monthly_incident_trends.csv" in tela
    assert "scripts/download_data.py" in tela


def test_tela_tem_uma_linha_por_tabela_na_ordem_do_mapa_e_milhar_com_ponto(
    tmp_path, monkeypatch, capsys
):
    # 1.000 meses inventados: só para a contagem passar do milhar.
    mensal = "month,total_incidents\n" + "".join(f"m{i},1\n" for i in range(1000))
    csvs = {**CSVS, "monthly_incident_trends.csv": mensal}
    _preparar(tmp_path, monkeypatch, csvs)

    ingestao.main()

    linhas = capsys.readouterr().out.splitlines()
    assert [linha.split()[0] for linha in linhas] == [
        "raw.incidentes",
        "raw.incidentes_completo",
        "raw.tipos_ataque",
        "raw.tendencia_mensal",
        "total",
    ]
    assert linhas[3].split()[1] == "1.000"
    # 3 + 2 + 1 + 1.000
    assert linhas[4].split()[1] == "1.006"
