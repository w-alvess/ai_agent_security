"""Painel: leitura dos marts, formatação, filtro da lista e gráficos.

A página é app.py (uv run streamlit run app.py). Este módulo não importa
streamlit, para que um relatório HTML futuro reaproveite as mesmas funções.
Spec completa em specs/04_painel.md.

1. LEITURA
   ler(marts) -> dict nome -> DataFrame, só SELECT * FROM mart.<nome>.
   Caminho do banco resolvido a partir deste arquivo, nunca do diretório
   corrente. Conexão read_only, aberta e fechada dentro de ler(); não usa
   conectar() de pipeline/db.py.
   Por quê: conectar() cria o arquivo quando ele falta e abre para escrita,
   e conexão aberta segura o lock: pipeline.marts não grava com o painel de
   pé. Mart que não existe fica fora do dict; quem chama decide o erro.

2. NENHUM CÁLCULO
   Aqui e em app.py: nada de agrupar, somar, tirar média, contar, medir
   tamanho de dado, juntar tabelas, mudar de formato largo para longo ou
   deixar o plotly agregar (histogram, density_heatmap), nem conta entre
   colunas. Só ordenar, filtrar linhas, pegar as n primeiras, escolher qual
   coluna plotar, renomear coluna e formatar texto.
   Por quê: número novo na tela exige um .sql novo em sql/marts/; os
   cartões vêm prontos de mart.kpis por isso.

3. FORMATO
   numero(): milhar com ponto, decimal com vírgula, sem locale do sistema.
   Por quê: o resultado não pode depender da máquina de quem roda.
   data_texto(): 'day' mostra o dia; 'month' e 'part' só mês/ano; valor
   desconhecido mostra a data com a precisão ao lado.
   Por quê: 53 registros têm o dia inventado, e mostrá-lo seria afirmar o
   que o dado não disse; precisão nova aparece em vez de virar 'day'.

4. GRÁFICOS
   Uma função por gráfico, DataFrame do mart dentro, figura plotly fora.
   Título com o número do mart, eixo com unidade, uma cor só; o 04 usa
   quatro tons da mesma cor, porque é a soma das situações que a barra
   mostra.
   so_incidentes troca a coluna plotada pela versão natureza = 'incident'
   que o próprio mart guardou ao lado, e reordena por ela; nunca filtra
   nem soma. Por quê: cada mart deixou as duas leituras para quem lê.
   02 anota o mês parcial: sem marca, a queda de 2026-10 parece real.
   05 deixa GLOBAL fora das barras (321 achataria as outras 12) e o número
   dele vai para legenda_global(), para não sumir.

5. LISTA DE REGISTROS
   filtrar_registros(): "envolve pelo menos um de" nas listas, que é a
   regra qtd_envolvido de mart.tipos_ataque; filtro vazio = desligado.
   Por quê: o mart entregou listas para o filtro não reinventar o split.
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BANCO = Path(__file__).resolve().parent / "incidentes.duckdb"
SCHEMA = "mart"

MARTS = [
    "tipos_ataque",
    "tendencia_mensal",
    "coocorrencia_ataques",
    "evidencia",
    "regioes",
    "fontes",
    "incidentes_painel",
    "kpis",
]

COR = "#2a78d6"
# Do mais escuro ao mais claro, na ordem das colunas de dano.
TONS_DANO = ["#104281", "#256abf", "#5598e7", "#86b6ef"]
ROTULOS_DANO = {
    "qtd_dano_confirmado": "confirmado",
    "qtd_dano_negado": "negado",
    "qtd_dano_nao_se_aplica": "não se aplica",
    "qtd_dano_nao_informado": "não informado",
}


# --- leitura -----------------------------------------------------------------


def ler(marts: list[str]) -> dict[str, pd.DataFrame]:
    dados = {}
    con = duckdb.connect(BANCO, read_only=True)
    try:
        for nome in marts:
            try:
                dados[nome] = con.execute(f'SELECT * FROM "{SCHEMA}"."{nome}"').df()
            except duckdb.CatalogException:
                pass
    finally:
        con.close()
    return dados


# --- formato -----------------------------------------------------------------


def numero(valor, casas: int = 0) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.translate(str.maketrans({",": ".", ".": ","}))


def data_texto(data, precisao: str) -> str:
    if data is None or pd.isna(data):
        return ""
    if precisao == "day":
        return data.strftime("%d/%m/%Y")
    if precisao in ("month", "part"):
        return data.strftime("%m/%Y")
    return f"{data.strftime('%d/%m/%Y')} ({precisao})"


# --- lista de registros ------------------------------------------------------


def _envolve(lista, escolhidos: list[str]) -> bool:
    return lista is not None and any(c in lista for c in escolhidos)


def filtrar_registros(
    df: pd.DataFrame,
    naturezas: list[str],
    codigos: list[str],
    regioes: list[str],
    meses: tuple[str, str],
) -> pd.DataFrame:
    # mes é 'AAAA-MM': a ordem do texto é a ordem do tempo.
    linhas = df[(df["mes"] >= meses[0]) & (df["mes"] <= meses[1])]
    if naturezas:
        linhas = linhas[linhas["natureza"].isin(naturezas)]
    if codigos:
        linhas = linhas[linhas["codigos_ataque"].apply(_envolve, args=(codigos,))]
    if regioes:
        linhas = linhas[linhas["regioes"].apply(_envolve, args=(regioes,))]
    return linhas


def tabela_registros(df: pd.DataFrame) -> pd.DataFrame:
    tabela = df[
        [
            "titulo",
            "natureza",
            "severidade",
            "confianca",
            "situacao_dano",
            "codigos_ataque",
            "regioes",
            "qtd_fontes",
        ]
    ].copy()
    tabela.insert(
        0,
        "data",
        [data_texto(d, p) for d, p in zip(df["data"], df["precisao_data"])],
    )
    for coluna in ("codigos_ataque", "regioes"):
        tabela[coluna] = tabela[coluna].apply(lambda v: None if v is None else list(v))
    return tabela


# --- gráficos ----------------------------------------------------------------


def _coluna(geral: str, so_inc: str, so_incidentes: bool) -> str:
    return so_inc if so_incidentes else geral


def _unidade(so_incidentes: bool) -> str:
    return "incidentes" if so_incidentes else "registros"


def _layout(fig: go.Figure, titulo: str, altura: int = 380) -> go.Figure:
    fig.update_layout(
        title=titulo,
        height=altura,
        margin={"l": 8, "r": 8, "t": 48, "b": 8},
        showlegend=False,
    )
    return fig


def _barras_h(df: pd.DataFrame, x: str, y: str, titulo: str, unidade: str, hover=None):
    fig = px.bar(
        df,
        x=x,
        y=y,
        orientation="h",
        color_discrete_sequence=[COR],
        hover_data=hover,
    )
    # Plotly desenha a primeira categoria embaixo; invertido, a ordem do
    # DataFrame (maior primeiro) fica de cima para baixo.
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title=unidade)
    return _layout(fig, titulo)


def grafico_tendencia(df: pd.DataFrame, so_incidentes: bool) -> go.Figure:
    y = _coluna("total", "qtd_incident", so_incidentes)
    fig = px.line(df, x="mes", y=y, markers=True, color_discrete_sequence=[COR])
    fig.update_traces(line_width=2, marker_size=8)
    for _, linha in df[df["mes_parcial"]].iterrows():
        fig.add_annotation(x=linha["mes"], y=linha[y], text="parcial", showarrow=True)
    fig.update_xaxes(title="mês", type="category")
    fig.update_yaxes(title=f"{_unidade(so_incidentes)} por mês", rangemode="tozero")
    return _layout(fig, "02 · Tendência mensal")


def grafico_tipos(df: pd.DataFrame, so_incidentes: bool) -> go.Figure:
    x = _coluna("qtd_envolvido", "qtd_envolvido_so_incidentes", so_incidentes)
    ordenado = df.sort_values([x, "codigo"], ascending=[False, True])
    return _barras_h(
        ordenado,
        x,
        "codigo",
        "01 · Tipos de ataque (envolvido)",
        _unidade(so_incidentes),
        hover=["nome"],
    )


def grafico_coocorrencia(df: pd.DataFrame, so_incidentes: bool) -> go.Figure:
    tamanho = _coluna("qtd_juntos", "qtd_juntos_so_incidentes", so_incidentes)
    fig = px.scatter(
        df,
        x="codigo_a",
        y="codigo_b",
        size=tamanho,
        size_max=28,
        color_discrete_sequence=[COR],
        hover_data=["nome_a", "nome_b", tamanho],
    )
    fig.update_xaxes(title="tipo A", categoryorder="category ascending")
    fig.update_yaxes(title="tipo B", categoryorder="category ascending")
    titulo = f"03 · Coocorrência (tamanho = {_unidade(so_incidentes)} com os dois)"
    return _layout(fig, titulo, altura=420)


def grafico_dano(df: pd.DataFrame) -> go.Figure:
    ordenado = df.sort_values(["total", "natureza"], ascending=[False, True])
    ordenado = ordenado.rename(columns=ROTULOS_DANO)
    fig = px.bar(
        ordenado,
        y="natureza",
        x=list(ROTULOS_DANO.values()),
        orientation="h",
        color_discrete_sequence=TONS_DANO,
    )
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="registros")
    _layout(fig, "04 · Situação do dano por natureza")
    fig.update_layout(
        showlegend=True,
        legend={"title": None, "orientation": "h", "y": -0.2},
    )
    return fig


def grafico_regioes(df: pd.DataFrame, so_incidentes: bool) -> go.Figure:
    x = _coluna("qtd_envolvido", "qtd_envolvido_so_incidentes", so_incidentes)
    sem_global = df[df["escopo"] != "global"]
    ordenado = sem_global.sort_values([x, "regiao"], ascending=[False, True])
    return _barras_h(
        ordenado,
        x,
        "regiao",
        "05 · Regiões (sem GLOBAL)",
        _unidade(so_incidentes),
        hover=["escopo"],
    )


def legenda_global(df: pd.DataFrame, so_incidentes: bool) -> str | None:
    x = _coluna("qtd_envolvido", "qtd_envolvido_so_incidentes", so_incidentes)
    linha = df[df["regiao"] == "GLOBAL"]
    if linha.empty:
        return None
    return (
        f"GLOBAL: {numero(linha[x].iloc[0])} {_unidade(so_incidentes)}, fora do gráfico"
    )


def grafico_fontes(df: pd.DataFrame, so_incidentes: bool) -> go.Figure:
    x = _coluna("qtd_registros", "qtd_so_incidentes", so_incidentes)
    top = df.sort_values([x, "dominio"], ascending=[False, True]).head(10)
    return _barras_h(
        top, x, "dominio", "06 · Fontes (top 10 domínios)", _unidade(so_incidentes)
    )
