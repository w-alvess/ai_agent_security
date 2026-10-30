"""Testes de pipeline/transformacao.py: itens 1 a 7 da docstring do módulo."""

import duckdb
import pytest

from pipeline import db, transformacao

# As 31 colunas de raw.incidentes_completo: a transformação seleciona todas.
COLUNAS_INCIDENTES = [bruta for bruta, _, _ in transformacao.TABELAS["incidentes"][2]]

TABELAS_REFINED = {
    "incidentes",
    "tipos_ataque",
    "tendencia_mensal",
    "incidente_tipos",
    "incidente_regioes",
    "fontes",
}


def _incidente(**valores):
    # Um incidente válido; cada teste troca só o campo que interessa.
    linha = {c: "x" for c in COLUNAS_INCIDENTES}
    linha.update(
        {
            "id": "INC-1",
            "date": "2025-01-10",
            "date_end": None,
            "date_precision": "day",
            "month": "2025-01",
            "kind": "incident",
            "type": "IPI",
            "region": "US",
            "real_harm": "true",
            "disputed": "false",
            "landmark": "false",
            "sources": "https://a.com/1",
        }
    )
    linha.update(valores)
    return linha


def _tipo(**valores):
    return {"type_code": "IPI", "type_name": "Injection", "incident_count": "1", "description": "d"} | valores


def _mes(**valores):
    linha = {
        "month": "2025-01",
        "total_incidents": "1",
        "critical_incidents": "0",
        "high_severity_incidents": "1",
        "medium_severity_incidents": "0",
        "real_harm_confirmed": "1",
    }
    return linha | valores


def _preparar(tmp_path, monkeypatch, incidentes=None, tipos=None, meses=None, sem=()):
    banco = tmp_path / "incidentes.duckdb"
    monkeypatch.setattr(db, "_BANCO", banco)
    tabelas = {
        "incidentes_completo": incidentes or [_incidente()],
        "tipos_ataque": tipos or [_tipo()],
        "tendencia_mensal": meses or [_mes()],
    }
    con = duckdb.connect(banco)
    con.execute("CREATE SCHEMA raw")
    for nome, linhas in tabelas.items():
        if nome in sem:
            continue
        colunas = list(linhas[0])
        con.execute(
            f"CREATE TABLE raw.{nome} (" + ", ".join(f'"{c}" VARCHAR' for c in colunas) + ")"
        )
        con.executemany(
            f"INSERT INTO raw.{nome} VALUES ({', '.join('?' for _ in colunas)})",
            [list(linha.values()) for linha in linhas],
        )
    con.close()
    return banco


def _consultar(banco, sql):
    con = duckdb.connect(banco)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _tabelas(banco, schema):
    return {
        t
        for (t,) in _consultar(
            banco, f"SELECT table_name FROM duckdb_tables() WHERE schema_name = '{schema}'"
        )
    }


def _tipo_coluna(banco, tabela, coluna):
    return _consultar(
        banco,
        "SELECT data_type FROM duckdb_columns() WHERE schema_name = 'refined' "
        f"AND table_name = '{tabela}' AND column_name = '{coluna}'",
    )[0][0]


def _encerra_sem_gravar(banco):
    with pytest.raises(SystemExit) as saida:
        transformacao.main()
    assert saida.value.code == 1
    assert _tabelas(banco, "refined") == set()


def test_saem_as_seis_tabelas_refined_e_raw_incidentes_fica_de_fora(tmp_path, monkeypatch):
    banco = _preparar(tmp_path, monkeypatch)
    con = duckdb.connect(banco)
    # raw.incidentes existe em raw, mas não entra.
    con.execute("CREATE TABLE raw.incidentes AS SELECT 'INC-1' AS id")
    con.close()

    transformacao.main()

    assert _tabelas(banco, "refined") == TABELAS_REFINED


def test_raw_fica_intacto(tmp_path, monkeypatch):
    banco = _preparar(tmp_path, monkeypatch)
    antes = _consultar(banco, "SELECT * FROM raw.incidentes_completo")

    transformacao.main()

    assert _consultar(banco, "SELECT * FROM raw.incidentes_completo") == antes
    assert _tabelas(banco, "raw") == {"incidentes_completo", "tipos_ataque", "tendencia_mensal"}


def test_colunas_sao_renomeadas_pelo_mapa(tmp_path, monkeypatch):
    banco = _preparar(tmp_path, monkeypatch, incidentes=[_incidente(id="INC-7", real_harm="false")])

    transformacao.main()

    assert _consultar(banco, "SELECT incidente_id, dano_real FROM refined.incidentes") == [
        ("INC-7", False)
    ]


def test_datas_viram_date_booleanos_boolean_contagens_integer_e_mes_continua_varchar(
    tmp_path, monkeypatch
):
    banco = _preparar(tmp_path, monkeypatch, incidentes=[_incidente(date_end="2025-01-12")])

    transformacao.main()

    assert _tipo_coluna(banco, "incidentes", "data") == "DATE"
    assert _tipo_coluna(banco, "incidentes", "data_fim") == "DATE"
    assert _tipo_coluna(banco, "incidentes", "dano_real") == "BOOLEAN"
    assert _tipo_coluna(banco, "incidentes", "contestado") == "BOOLEAN"
    assert _tipo_coluna(banco, "incidentes", "marco") == "BOOLEAN"
    assert _tipo_coluna(banco, "incidentes", "mes") == "VARCHAR"
    assert _tipo_coluna(banco, "tipos_ataque", "qtd_incidentes") == "INTEGER"
    assert _tipo_coluna(banco, "tendencia_mensal", "total_incidentes") == "INTEGER"
    assert _tipo_coluna(banco, "incidente_tipos", "posicao") == "INTEGER"


def test_dano_real_nulo_continua_nulo_e_nao_vira_false(tmp_path, monkeypatch):
    incidentes = [
        # Registro de natureza policy: "houve dano?" não se aplica.
        _incidente(id="INC-1", kind="policy", real_harm=None),
        _incidente(id="INC-2", real_harm="false"),
    ]
    banco = _preparar(tmp_path, monkeypatch, incidentes=incidentes)

    transformacao.main()

    assert _consultar(banco, "SELECT incidente_id, dano_real FROM refined.incidentes") == [
        ("INC-1", None),
        ("INC-2", False),
    ]


def test_yes_num_booleano_encerra_sem_gravar(tmp_path, monkeypatch, capsys):
    # 'yes' seria aceito calado por CAST AS BOOLEAN.
    banco = _preparar(tmp_path, monkeypatch, incidentes=[_incidente(disputed="yes")])

    _encerra_sem_gravar(banco)

    tela = capsys.readouterr().out
    assert "refined.incidentes.contestado" in tela
    assert "yes" in tela


def test_data_fora_do_formato_encerra_sem_virar_nulo(tmp_path, monkeypatch, capsys):
    banco = _preparar(tmp_path, monkeypatch, incidentes=[_incidente(date="10/01/2025")])

    _encerra_sem_gravar(banco)

    assert "refined.incidentes.data " in capsys.readouterr().out


def test_inteiro_invalido_encerra_sem_gravar(tmp_path, monkeypatch):
    banco = _preparar(tmp_path, monkeypatch, tipos=[_tipo(incident_count="doze")])

    _encerra_sem_gravar(banco)


def test_duplicata_exata_sai_e_a_tela_diz_quantas(tmp_path, monkeypatch, capsys):
    # A mesma linha duas vezes: fica uma.
    banco = _preparar(tmp_path, monkeypatch, tipos=[_tipo(), _tipo()])

    transformacao.main()

    assert _consultar(banco, "SELECT count(*) FROM refined.tipos_ataque")[0][0] == 1
    linha = next(
        linha
        for linha in capsys.readouterr().out.splitlines()
        if linha.startswith("refined.tipos_ataque")
    )
    assert linha.split() == ["refined.tipos_ataque", "2", "->", "1", "linhas", "(1", "duplicatas)"]


def test_chave_repetida_com_conteudo_diferente_encerra_sem_gravar(tmp_path, monkeypatch):
    # Mesmo codigo, nomes diferentes: escolher um seria decidir em silêncio.
    tipos = [_tipo(type_name="Injection"), _tipo(type_name="Prompt injection")]
    banco = _preparar(tmp_path, monkeypatch, tipos=tipos)

    _encerra_sem_gravar(banco)


def test_codigos_separados_por_ponto_e_virgula_viram_duas_linhas_na_ponte(tmp_path, monkeypatch):
    # Incidente com dois tipos.
    banco = _preparar(tmp_path, monkeypatch, incidentes=[_incidente(type="IPI;EXFIL")])

    transformacao.main()

    assert _consultar(
        banco, "SELECT incidente_id, posicao, codigo_ataque FROM refined.incidente_tipos"
    ) == [("INC-1", 1, "IPI"), ("INC-1", 2, "EXFIL")]
    # A string original continua em refined.incidentes.
    assert _consultar(banco, "SELECT codigos_ataque FROM refined.incidentes") == [("IPI;EXFIL",)]


def test_ponte_nao_faz_trim(tmp_path, monkeypatch):
    # Espaço depois do ';': chega com o espaço, ninguém decide que é igual.
    banco = _preparar(tmp_path, monkeypatch, incidentes=[_incidente(region="US; EU")])

    transformacao.main()

    assert _consultar(banco, "SELECT regiao FROM refined.incidente_regioes ORDER BY posicao") == [
        ("US",),
        (" EU",),
    ]


def test_pedaco_vazio_encerra_sem_gravar(tmp_path, monkeypatch, capsys):
    # 'IPI;' tem um pedaço vazio depois do ';'.
    banco = _preparar(tmp_path, monkeypatch, incidentes=[_incidente(type="IPI;")])

    _encerra_sem_gravar(banco)

    assert "Pedaço vazio" in capsys.readouterr().out


def test_tabela_faltando_em_raw_encerra(tmp_path, monkeypatch, capsys):
    banco = _preparar(tmp_path, monkeypatch, sem=("tendencia_mensal",))

    _encerra_sem_gravar(banco)

    tela = capsys.readouterr().out
    assert "raw.tendencia_mensal" in tela
    assert "uv run python -m pipeline.ingestao" in tela


def test_rodar_duas_vezes_da_o_mesmo_resultado(tmp_path, monkeypatch, capsys):
    banco = _preparar(tmp_path, monkeypatch, incidentes=[_incidente(type="IPI;EXFIL")])

    transformacao.main()
    primeira = capsys.readouterr().out
    transformacao.main()
    segunda = capsys.readouterr().out

    assert primeira == segunda
    assert _consultar(banco, "SELECT count(*) FROM refined.incidente_tipos")[0][0] == 2


def test_tela_mostra_as_colunas_com_nulo(tmp_path, monkeypatch, capsys):
    # date_end nulo: incidente de um dia só.
    _preparar(tmp_path, monkeypatch)

    transformacao.main()

    assert "    nulos mantidos: data_fim 1" in capsys.readouterr().out.splitlines()
