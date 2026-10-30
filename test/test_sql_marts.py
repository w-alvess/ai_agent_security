"""Testes de sql/marts/01, 02, 03 e 08, rodados sobre refined inventado.

Os .sql são lidos do projeto (são código); as tabelas refined são do teste,
só com as colunas que cada .sql lê.
"""

from datetime import date
from pathlib import Path

import duckdb

PASTA_SQL = Path(__file__).resolve().parent.parent / "sql" / "marts"


def _banco(tmp_path, tabelas):
    """tabelas: nome -> (definição das colunas, linhas)."""
    con = duckdb.connect(tmp_path / "t.duckdb")
    con.execute("CREATE SCHEMA refined")
    for nome, (colunas, linhas) in tabelas.items():
        con.execute(f"CREATE TABLE refined.{nome} ({colunas})")
        if linhas:
            marcas = ", ".join("?" for _ in linhas[0])
            con.executemany(f"INSERT INTO refined.{nome} VALUES ({marcas})", linhas)
    return con


def _rodar(con, arquivo):
    cursor = con.execute((PASTA_SQL / arquivo).read_text(encoding="utf-8"))
    colunas = [d[0] for d in cursor.description]
    linhas = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    con.close()
    return linhas


# --- 01_tipos_ataque ---------------------------------------------------------


def _tipos_ataque(tmp_path):
    con = _banco(
        tmp_path,
        {
            "tipos_ataque": (
                "codigo VARCHAR, nome VARCHAR",
                [
                    ("CRED", "Credenciais"),
                    ("IPI", "Injeção indireta"),
                    # OTHER: tipo sem nenhum incidente.
                    ("OTHER", "Outro"),
                ],
            ),
            "incidentes": (
                "incidente_id VARCHAR, codigos_ataque VARCHAR, natureza VARCHAR, "
                "severidade VARCHAR, dano_real BOOLEAN",
                [
                    # I1: dois tipos, CRED em primeiro; crítico, dano confirmado.
                    ("I1", "CRED;IPI", "incident", "critical", True),
                    # I2: só CRED; policy com dano nulo -> nao_se_aplica.
                    ("I2", "CRED", "policy", "low", None),
                    # I3: só IPI; incident com dano nulo -> nao_informado.
                    ("I3", "IPI", "incident", "high", None),
                ],
            ),
            "incidente_tipos": (
                "incidente_id VARCHAR, posicao INTEGER, codigo_ataque VARCHAR",
                [("I1", 1, "CRED"), ("I1", 2, "IPI"), ("I2", 1, "CRED"), ("I3", 1, "IPI")],
            ),
        },
    )
    return {linha["codigo"]: linha for linha in _rodar(con, "01_tipos_ataque.sql")}


def test_incidente_com_dois_tipos_conta_uma_vez_no_tipo_principal(tmp_path):
    tipos = _tipos_ataque(tmp_path)

    # I1 conta só para CRED (posição 1): três incidentes, três no total.
    assert tipos["CRED"]["qtd_tipo_principal"] == 2
    assert tipos["IPI"]["qtd_tipo_principal"] == 1
    assert sum(t["qtd_tipo_principal"] for t in tipos.values()) == 3


def test_incidente_com_dois_tipos_conta_em_qtd_envolvido_de_cada_tipo(tmp_path):
    tipos = _tipos_ataque(tmp_path)

    assert tipos["CRED"]["qtd_envolvido"] == 2
    assert tipos["IPI"]["qtd_envolvido"] == 2


def test_incidente_com_dois_tipos_fica_fora_do_tipo_unico(tmp_path):
    tipos = _tipos_ataque(tmp_path)

    # Só I2 é 'CRED' sozinho e só I3 é 'IPI' sozinho.
    assert tipos["CRED"]["qtd_tipo_unico"] == 1
    assert tipos["IPI"]["qtd_tipo_unico"] == 1


def test_tipo_sem_incidente_aparece_com_zero(tmp_path):
    outro = _tipos_ataque(tmp_path)["OTHER"]

    assert outro["qtd_envolvido"] == 0
    assert outro["qtd_tipo_principal"] == 0
    assert outro["qtd_dano_nao_informado"] == 0


def test_dano_nulo_em_policy_nao_se_aplica_e_em_incident_nao_informado(tmp_path):
    tipos = _tipos_ataque(tmp_path)

    # CRED: I1 confirmado, I2 policy nulo.
    assert tipos["CRED"]["qtd_dano_confirmado"] == 1
    assert tipos["CRED"]["qtd_dano_nao_se_aplica"] == 1
    assert tipos["CRED"]["qtd_dano_nao_informado"] == 0
    # IPI: I1 confirmado, I3 incident nulo.
    assert tipos["IPI"]["qtd_dano_nao_se_aplica"] == 0
    assert tipos["IPI"]["qtd_dano_nao_informado"] == 1


def test_so_incidentes_conta_so_natureza_incident(tmp_path):
    tipos = _tipos_ataque(tmp_path)

    # CRED tem I1 (incident) e I2 (policy).
    assert tipos["CRED"]["qtd_envolvido_so_incidentes"] == 1
    assert tipos["IPI"]["qtd_envolvido_so_incidentes"] == 2


# --- 02_tendencia_mensal -----------------------------------------------------


def _tendencia(tmp_path, ultima_data):
    con = _banco(
        tmp_path,
        {
            "incidentes": (
                "incidente_id VARCHAR, mes VARCHAR, data DATE, data_fim DATE, "
                "natureza VARCHAR, severidade VARCHAR, dano_real BOOLEAN",
                [
                    ("I1", "2025-01", date(2025, 1, 10), None, "incident", "critical", True),
                    # 2025-02 fica sem registro.
                    # I2 começa em março e vai até abril: conta só em março.
                    ("I2", "2025-03", date(2025, 3, 5), date(2025, 4, 20), "policy", "high", None),
                    # I3 tem a maior data: decide se abril é parcial.
                    ("I3", "2025-04", ultima_data, None, "research", "medium", False),
                ],
            ),
        },
    )
    return {linha["mes"]: linha for linha in _rodar(con, "02_tendencia_mensal.sql")}


def test_mes_sem_registro_aparece_com_zero(tmp_path):
    meses = _tendencia(tmp_path, date(2025, 4, 30))

    assert list(meses) == ["2025-01", "2025-02", "2025-03", "2025-04"]
    assert meses["2025-02"]["total"] == 0


def test_incidente_com_data_fim_conta_uma_vez_no_mes_de_inicio(tmp_path):
    meses = _tendencia(tmp_path, date(2025, 4, 30))

    assert meses["2025-03"]["total"] == 1
    # Abril tem só I3.
    assert meses["2025-04"]["total"] == 1
    assert sum(m["total"] for m in meses.values()) == 3


def test_mes_parcial_so_no_mes_da_maior_data_quando_ela_nao_e_o_ultimo_dia(tmp_path):
    meses = _tendencia(tmp_path, date(2025, 4, 12))

    assert [m for m, linha in meses.items() if linha["mes_parcial"]] == ["2025-04"]


def test_maior_data_no_ultimo_dia_do_mes_nao_marca_parcial(tmp_path):
    meses = _tendencia(tmp_path, date(2025, 4, 30))

    assert not any(linha["mes_parcial"] for linha in meses.values())


def test_tendencia_separa_natureza_e_severidade(tmp_path):
    marco = _tendencia(tmp_path, date(2025, 4, 30))["2025-03"]

    assert (marco["qtd_policy"], marco["qtd_incident"], marco["qtd_alta"]) == (1, 0, 1)


# --- 03_coocorrencia_ataques -------------------------------------------------


def _coocorrencia(tmp_path):
    con = _banco(
        tmp_path,
        {
            "tipos_ataque": (
                "codigo VARCHAR, nome VARCHAR",
                # OTHER nunca aparece com ninguém.
                [("CRED", "c"), ("EXFIL", "e"), ("IPI", "i"), ("OTHER", "o")],
            ),
            "incidentes": (
                "incidente_id VARCHAR, natureza VARCHAR",
                [("I1", "incident"), ("I2", "research")],
            ),
            "incidente_tipos": (
                "incidente_id VARCHAR, posicao INTEGER, codigo_ataque VARCHAR",
                [
                    # I1: três tipos, IPI antes de EXFIL na ordem da fonte.
                    ("I1", 1, "IPI"),
                    ("I1", 2, "EXFIL"),
                    ("I1", 3, "CRED"),
                    # I2: dois tipos.
                    ("I2", 1, "IPI"),
                    ("I2", 2, "EXFIL"),
                ],
            ),
        },
    )
    return {(p["codigo_a"], p["codigo_b"]): p for p in _rodar(con, "03_coocorrencia_ataques.sql")}


def test_todos_os_pares_possiveis_aparecem_com_codigo_a_menor_que_b(tmp_path):
    pares = _coocorrencia(tmp_path)

    # 4 tipos -> 6 pares sem ordem.
    assert len(pares) == 6
    assert all(a < b for a, b in pares)


def test_incidente_com_tres_tipos_gera_tres_pares(tmp_path):
    pares = _coocorrencia(tmp_path)

    # Só I1 é incident: cada um dos seus três pares conta 1.
    so_incidentes = {k: p["qtd_juntos_so_incidentes"] for k, p in pares.items() if p["qtd_juntos_so_incidentes"]}
    assert so_incidentes == {("CRED", "EXFIL"): 1, ("CRED", "IPI"): 1, ("EXFIL", "IPI"): 1}


def test_par_sem_ordem_soma_os_dois_incidentes(tmp_path):
    pares = _coocorrencia(tmp_path)

    # IPI vem antes de EXFIL nos dois: o par é (EXFIL, IPI).
    assert pares[("EXFIL", "IPI")]["qtd_juntos"] == 2


def test_par_que_nunca_aparece_junto_vem_com_zero(tmp_path):
    pares = _coocorrencia(tmp_path)

    assert pares[("CRED", "OTHER")]["qtd_juntos"] == 0
    assert pares[("CRED", "OTHER")]["qtd_envolvido_b"] == 0
    assert pares[("CRED", "OTHER")]["qtd_envolvido_a"] == 1


# --- 08_kpis -----------------------------------------------------------------


def test_registro_sem_url_fica_fora_de_qtd_fonte_unica(tmp_path):
    con = _banco(
        tmp_path,
        {
            "incidentes": (
                "incidente_id VARCHAR, natureza VARCHAR, severidade VARCHAR, "
                "dano_real BOOLEAN, contestado BOOLEAN",
                [
                    ("I1", "incident", "critical", True, False),
                    ("I2", "policy", "low", None, True),
                    ("I3", "research", "high", False, False),
                ],
            ),
            "fontes": (
                "incidente_id VARCHAR, posicao INTEGER, url VARCHAR",
                [
                    # I1: uma URL. I2: duas. I3: nenhuma.
                    ("I1", 1, "https://a.com/1"),
                    ("I2", 1, "https://a.com/2"),
                    ("I2", 2, "https://b.com/2"),
                ],
            ),
        },
    )

    kpis = _rodar(con, "08_kpis.sql")

    assert kpis == [
        {
            "qtd_registros": 3,
            "qtd_incidentes": 1,
            "qtd_criticos": 1,
            "qtd_dano_confirmado": 1,
            "qtd_contestados": 1,
            "qtd_fonte_unica": 1,
        }
    ]
