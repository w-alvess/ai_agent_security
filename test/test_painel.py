"""Testes de painel.py: itens 1, 3, 4 e 5 da docstring do módulo."""

import duckdb
import pandas as pd

import painel

# --- leitura -----------------------------------------------------------------


def _banco_com_mart(tmp_path, monkeypatch):
    banco = tmp_path / "incidentes.duckdb"
    con = duckdb.connect(banco)
    con.execute("CREATE SCHEMA mart")
    con.execute("CREATE TABLE mart.kpis AS SELECT * FROM (VALUES (7), (8)) AS t(qtd)")
    con.close()
    monkeypatch.setattr(painel, "BANCO", banco)
    return banco


def test_ler_devolve_os_marts_pedidos(tmp_path, monkeypatch):
    _banco_com_mart(tmp_path, monkeypatch)

    dados = painel.ler(["kpis"])

    assert dados["kpis"]["qtd"].tolist() == [7, 8]


def test_mart_que_nao_existe_fica_fora_do_dict(tmp_path, monkeypatch):
    _banco_com_mart(tmp_path, monkeypatch)

    dados = painel.ler(["kpis", "nao_existe"])

    assert list(dados) == ["kpis"]


def test_ler_fecha_a_conexao(tmp_path, monkeypatch):
    banco = _banco_com_mart(tmp_path, monkeypatch)
    painel.ler(["kpis"])

    # Com a conexão read_only ainda aberta, abrir para escrita falharia.
    con = duckdb.connect(banco)
    con.execute("DROP TABLE mart.kpis")
    restantes = con.execute("SELECT count(*) FROM duckdb_tables()").fetchall()
    con.close()

    assert restantes == [(0,)]


# --- formato -----------------------------------------------------------------


def test_numero_inteiro_tem_milhar_com_ponto():
    assert painel.numero(1234) == "1.234"
    assert painel.numero(999) == "999"
    assert painel.numero(0) == "0"


def test_numero_milhao_tem_dois_pontos():
    assert painel.numero(1234567) == "1.234.567"


def test_numero_com_casas_tem_decimal_com_virgula():
    assert painel.numero(1234.5, 1) == "1.234,5"
    assert painel.numero(0.25, 2) == "0,25"


def test_data_texto_day_mostra_o_dia():
    assert painel.data_texto(pd.Timestamp("2025-03-07"), "day") == "07/03/2025"


def test_data_texto_month_e_part_nao_mostram_o_dia():
    # Dia 01 e dia 15 inventados pela fonte.
    assert painel.data_texto(pd.Timestamp("2025-03-01"), "month") == "03/2025"
    assert painel.data_texto(pd.Timestamp("2025-03-15"), "part") == "03/2025"


def test_data_texto_precisao_desconhecida_mostra_a_precisao_ao_lado():
    assert painel.data_texto(pd.Timestamp("2025-03-07"), "week") == "07/03/2025 (week)"


def test_data_texto_data_nula_fica_vazia():
    assert painel.data_texto(None, "day") == ""
    assert painel.data_texto(pd.NaT, "day") == ""


# --- lista de registros ------------------------------------------------------


def _registros():
    return pd.DataFrame(
        {
            "titulo": ["r1", "r2", "r3"],
            "mes": ["2025-01", "2025-02", "2025-03"],
            "data": pd.to_datetime(["2025-01-10", "2025-02-01", "2025-03-15"]),
            "precisao_data": ["day", "month", "part"],
            "natureza": ["incident", "policy", "research"],
            "severidade": ["high", "low", "medium"],
            "confianca": ["A", "B", "C"],
            "situacao_dano": ["confirmado", "nao_se_aplica", "negado"],
            # r1 tem dois tipos; r3 não tem tipo nenhum (lista nula).
            "codigos_ataque": [["CRED", "IPI"], ["GOV"], None],
            "regioes": [["US"], ["EU"], ["GLOBAL"]],
            "qtd_fontes": [1, 2, 1],
        }
    )


TODO_PERIODO = ("2025-01", "2025-03")


def test_filtro_vazio_fica_desligado():
    filtrado = painel.filtrar_registros(_registros(), [], [], [], TODO_PERIODO)

    assert filtrado["titulo"].tolist() == ["r1", "r2", "r3"]


def test_filtro_de_tipo_traz_quem_envolve_pelo_menos_um():
    filtrado = painel.filtrar_registros(_registros(), [], ["IPI", "GOV"], [], TODO_PERIODO)

    assert filtrado["titulo"].tolist() == ["r1", "r2"]


def test_lista_nula_nao_quebra_o_filtro():
    filtrado = painel.filtrar_registros(_registros(), [], ["CRED"], [], TODO_PERIODO)

    assert filtrado["titulo"].tolist() == ["r1"]


def test_filtro_de_natureza_e_de_regiao():
    df = _registros()

    assert painel.filtrar_registros(df, ["policy"], [], [], TODO_PERIODO)["titulo"].tolist() == ["r2"]
    assert painel.filtrar_registros(df, [], [], ["GLOBAL"], TODO_PERIODO)["titulo"].tolist() == ["r3"]


def test_periodo_inclui_as_duas_pontas():
    filtrado = painel.filtrar_registros(_registros(), [], [], [], ("2025-02", "2025-03"))

    assert filtrado["titulo"].tolist() == ["r2", "r3"]


def test_tabela_registros_poe_a_data_formatada_na_frente():
    tabela = painel.tabela_registros(_registros())

    assert tabela.columns[0] == "data"
    assert tabela["data"].tolist() == ["10/01/2025", "02/2025", "03/2025"]
    assert tabela["codigos_ataque"].tolist() == [["CRED", "IPI"], ["GOV"], None]


# --- gráficos ----------------------------------------------------------------


def _tendencia():
    return pd.DataFrame(
        {
            "mes": ["2025-01", "2025-02", "2025-03"],
            # Só o último mês é parcial.
            "mes_parcial": [False, False, True],
            "total": [5, 0, 2],
            "qtd_incident": [3, 0, 1],
        }
    )


def test_tendencia_tem_um_ponto_por_mes():
    fig = painel.grafico_tendencia(_tendencia(), so_incidentes=False)

    assert list(fig.data[0].x) == ["2025-01", "2025-02", "2025-03"]
    assert list(fig.data[0].y) == [5, 0, 2]


def test_tendencia_so_incidentes_plota_qtd_incident():
    fig = painel.grafico_tendencia(_tendencia(), so_incidentes=True)

    assert list(fig.data[0].y) == [3, 0, 1]


def test_tendencia_anota_parcial_so_no_mes_marcado():
    fig = painel.grafico_tendencia(_tendencia(), so_incidentes=False)

    assert [(a.x, a.text) for a in fig.layout.annotations] == [("2025-03", "parcial")]


def _tipos():
    return pd.DataFrame(
        {
            "codigo": ["CRED", "GOV", "IPI"],
            "nome": ["c", "g", "i"],
            # GOV lidera no geral, mas tem 0 incidentes.
            "qtd_envolvido": [4, 9, 2],
            "qtd_envolvido_so_incidentes": [3, 0, 2],
        }
    )


def test_tipos_tem_uma_barra_por_tipo_maior_primeiro():
    fig = painel.grafico_tipos(_tipos(), so_incidentes=False)

    assert list(fig.data[0].y) == ["GOV", "CRED", "IPI"]
    assert list(fig.data[0].x) == [9, 4, 2]


def test_tipos_so_incidentes_troca_a_coluna_e_reordena():
    fig = painel.grafico_tipos(_tipos(), so_incidentes=True)

    assert list(fig.data[0].y) == ["CRED", "IPI", "GOV"]
    assert list(fig.data[0].x) == [3, 2, 0]


def test_coocorrencia_tem_um_ponto_por_par():
    pares = pd.DataFrame(
        {
            "codigo_a": ["CRED", "CRED", "EXFIL"],
            "nome_a": ["c", "c", "e"],
            "codigo_b": ["EXFIL", "IPI", "IPI"],
            "nome_b": ["e", "i", "i"],
            "qtd_juntos": [1, 0, 2],
            "qtd_juntos_so_incidentes": [1, 0, 1],
        }
    )

    fig = painel.grafico_coocorrencia(pares, so_incidentes=False)

    assert len(fig.data[0].x) == 3
    assert list(fig.data[0].marker.size) == [1, 0, 2]


def test_dano_tem_quatro_series_com_uma_barra_por_natureza():
    evidencia = pd.DataFrame(
        {
            "natureza": ["incident", "policy"],
            "total": [3, 2],
            "qtd_dano_confirmado": [2, 0],
            "qtd_dano_negado": [1, 0],
            # policy inteira em nao_se_aplica.
            "qtd_dano_nao_se_aplica": [0, 2],
            "qtd_dano_nao_informado": [0, 0],
        }
    )

    fig = painel.grafico_dano(evidencia)

    assert [t.name for t in fig.data] == ["confirmado", "negado", "não se aplica", "não informado"]
    assert all(len(t.y) == 2 for t in fig.data)


def _regioes():
    return pd.DataFrame(
        {
            "regiao": ["GLOBAL", "US", "EU"],
            "escopo": ["global", "local", "regional"],
            "qtd_envolvido": [1200, 5, 7],
            "qtd_envolvido_so_incidentes": [40, 3, 1],
        }
    )


def test_regioes_deixa_global_fora_das_barras():
    fig = painel.grafico_regioes(_regioes(), so_incidentes=False)

    assert list(fig.data[0].y) == ["EU", "US"]


def test_legenda_global_traz_o_numero_do_global():
    assert painel.legenda_global(_regioes(), False) == "GLOBAL: 1.200 registros, fora do gráfico"
    assert painel.legenda_global(_regioes(), True) == "GLOBAL: 40 incidentes, fora do gráfico"


def test_legenda_global_sem_global_devolve_none():
    sem_global = _regioes().iloc[1:]

    assert painel.legenda_global(sem_global, False) is None


def _fontes(n):
    return pd.DataFrame(
        {
            "dominio": [f"d{i:02}.com" for i in range(n)],
            "qtd_registros": list(range(n, 0, -1)),
            "qtd_so_incidentes": [1] * n,
        }
    )


def test_fontes_tem_uma_barra_por_dominio():
    fig = painel.grafico_fontes(_fontes(3), so_incidentes=False)

    assert list(fig.data[0].y) == ["d00.com", "d01.com", "d02.com"]


def test_fontes_mostra_no_maximo_dez_dominios():
    # 12 domínios: os dois menores ficam fora.
    fig = painel.grafico_fontes(_fontes(12), so_incidentes=False)

    assert len(fig.data[0].y) == 10
    assert "d10.com" not in list(fig.data[0].y)
