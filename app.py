"""Página do painel. Executar com:  uv run streamlit run app.py

Spec em specs/04_painel.md e resumida na docstring de painel.py. Aqui só
layout e controles: leitura, formato, filtro e gráficos moram em painel.py.
"""

import duckdb
import streamlit as st

import painel

COMANDO_MARTS = "uv run python -m pipeline.marts"
COMANDOS_PIPELINE = [
    "uv run python -m pipeline.ingestao",
    "uv run python -m pipeline.transformacao",
    COMANDO_MARTS,
]


@st.cache_data
def carregar() -> dict:
    return painel.ler(painel.MARTS)


st.set_page_config(page_title="Incidentes com agentes de IA", layout="wide")

esquerda, direita = st.columns([3, 2])
esquerda.title("Incidentes de segurança com agentes de IA · 2024-26")
# O botão vem antes da leitura: precisa aparecer também nas telas de erro.
if direita.button("Recarregar dados"):
    st.cache_data.clear()

if not painel.BANCO.is_file():
    st.error(
        f"Banco não encontrado: {painel.BANCO}\n\nRode, nesta ordem:\n\n"
        + "\n".join(f"- `{comando}`" for comando in COMANDOS_PIPELINE)
    )
    st.stop()

try:
    dados = carregar()
except duckdb.IOException:
    st.error(
        "O banco está sendo usado por outro processo (provavelmente "
        "pipeline.marts gravando). Clique em “Recarregar dados” quando ele terminar."
    )
    st.stop()

faltando = [nome for nome in painel.MARTS if nome not in dados]
if faltando:
    st.error(
        "Marts faltando: "
        + ", ".join(f"mart.{nome}" for nome in faltando)
        + f"\n\nRode: `{COMANDO_MARTS}`"
    )
    st.stop()

meses = dados["tendencia_mensal"]["mes"].tolist()
periodo = direita.select_slider("Período", options=meses, value=(meses[0], meses[-1]))
direita.caption("cartões e gráficos 01, 03 a 06 valem para o período inteiro")
so_incidentes = direita.toggle("Só incidentes")
direita.caption(
    "troca 01, 02, 03, 05 e 06 para natureza incident; não muda cartões, 04 nem a lista"
)

# Faixa 1: cartões
kpis = dados["kpis"].iloc[0]
cartoes = [
    ("Registros · todas as naturezas", "qtd_registros"),
    ("Incidentes · natureza incident", "qtd_incidentes"),
    ("Críticos · severidade critical", "qtd_criticos"),
    ("Dano confirmado · dano_real true", "qtd_dano_confirmado"),
    ("Contestados · o próprio registro", "qtd_contestados"),
    ("Fonte única · uma URL só", "qtd_fonte_unica"),
]
for coluna, (rotulo, campo) in zip(st.columns(6), cartoes):
    coluna.metric(rotulo, painel.numero(kpis[campo]))

# Faixa 2: série mensal, a única recortada pelo período
tendencia = dados["tendencia_mensal"]
no_periodo = tendencia[
    (tendencia["mes"] >= periodo[0]) & (tendencia["mes"] <= periodo[1])
]
st.plotly_chart(painel.grafico_tendencia(no_periodo, so_incidentes), width="stretch")

# Faixa 3
c1, c2 = st.columns(2)
c1.plotly_chart(
    painel.grafico_tipos(dados["tipos_ataque"], so_incidentes), width="stretch"
)
c2.plotly_chart(
    painel.grafico_coocorrencia(dados["coocorrencia_ataques"], so_incidentes),
    width="stretch",
)

# Faixa 4
c1, c2, c3 = st.columns(3)
c1.plotly_chart(painel.grafico_dano(dados["evidencia"]), width="stretch")
c2.plotly_chart(
    painel.grafico_regioes(dados["regioes"], so_incidentes), width="stretch"
)
legenda = painel.legenda_global(dados["regioes"], so_incidentes)
if legenda:
    c2.caption(legenda)
c3.plotly_chart(painel.grafico_fontes(dados["fontes"], so_incidentes), width="stretch")

# Faixa 5: lista de registros
st.subheader("07 · Registros")
tipos = dados["tipos_ataque"]
nomes_tipo = dict(zip(tipos["codigo"], tipos["nome"]))
f1, f2, f3 = st.columns(3)
naturezas = f1.multiselect("Natureza", dados["evidencia"]["natureza"].tolist())
codigos = f2.multiselect(
    "Tipo de ataque",
    tipos["codigo"].tolist(),
    format_func=lambda c: f"{c} · {nomes_tipo[c]}",
)
regioes = f3.multiselect("Região", dados["regioes"]["regiao"].tolist())

registros = painel.filtrar_registros(
    dados["incidentes_painel"], naturezas, codigos, regioes, periodo
)
st.dataframe(
    painel.tabela_registros(registros),
    width="stretch",
    hide_index=True,
    column_config={
        "codigos_ataque": st.column_config.ListColumn("codigos_ataque"),
        "regioes": st.column_config.ListColumn("regioes"),
    },
)
