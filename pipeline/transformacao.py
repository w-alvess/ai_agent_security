"""Transformação: de raw para refined, onde cada decisão sobre o dado fica escrita.

Executar com:  uv run python -m pipeline.transformacao

1. ESCOPO
   Lê de raw, escreve em refined, nunca escreve em raw. Entram três tabelas
   (incidentes_completo, tipos_ataque, tendencia_mensal) e saem seis: as
   três, uma para uma, e as três pontes do item 2b.
   raw.incidentes fica de fora. Por quê: é uma projeção de
   incidentes_completo (mesmos 395 ids, as 12 colunas comuns idênticas), e
   o que ela tem a mais é pior: trocou os 87 nulos de real_harm por False,
   source_count vale 1 até em incidente com 8 fontes, primary_source_url é
   a lista inteira, e year e attack_type_name se derivam de outras colunas.

2. NOMES
   Colunas em português, snake_case, pelo mapa em TABELAS, completo e
   literal: nenhuma coluna fora dele, nenhuma descartada (traduções e
   caminhos entram, mesmo sem uso previsto).
   Por quê: é o vocabulário digitado de memória nos JOINs do mart.

2b. TABELAS-PONTE
   codigos_ataque, regioes e urls_fontes guardam vários valores separados
   por ';'. Cada uma vira uma tabela (incidente_id, posicao, valor), e a
   coluna original continua em refined.incidentes, inalterada. Pedaço
   vazio é conversão que falha; nada de trim ou de mudar maiúsculas.
   Por quê: 120 incidentes têm códigos como 'IPI;EXFIL', que não fazem
   JOIN com tipos_ataque; sem a ponte, cada mart reinventa o split.
   posicao guarda a ordem, que pode ser prioridade, e deixa o split
   reversível. A string original fica porque refined não apaga o que
   recebeu.

3. TIPOS
   data e data_fim: DATE com formato declarado '%Y-%m-%d'; precisao_data
   fica ao lado. Por quê: 47 datas de precisão 'month' estão no dia 01 e 6
   de precisão 'part' no dia 15, ou seja, dias inventados. Apagar o dia
   apagaria o mês junto; quem lê decide quanto confiar olhando a precisão.
   mes continua VARCHAR 'AAAA-MM'. Por quê: é período, não dia; como DATE
   ganharia um dia 01 que não existe. É a chave entre incidentes e
   tendencia_mensal.
   dano_real, contestado, marco: BOOLEAN, aceitando só 'true' e 'false'.
   Por quê: CAST(... AS BOOLEAN) aceita calado 'yes', 'T' e '1'; valor
   fora do vocabulário quer dizer que a fonte mudou, e isso tem que
   aparecer.
   Contagens e posicao: INTEGER. Todo o resto VARCHAR, sem mudar
   maiúsculas. Por quê: severidade, confianca etc. são rótulos;
   normalizar 'A' para 'a' é decidir que são iguais sem o dado dizer.
   Conversão em SQL pelo DuckDB. Por quê: o dado já está no banco; não há
   por que trazê-lo para a memória só para converter tipo.

4. CONVERSÃO QUE FALHA
   strptime, CAST e error(), que estouram; nunca try_strptime nem TRY_CAST.
   Ao falhar: tabela, coluna e o valor, sys.exit(1), nada gravado.
   Por quê: um nulo fabricado pela conversão fica indistinguível de um
   nulo verdadeiro do dado, para sempre.

5. DUPLICATAS
   Chaves: incidentes (incidente_id), tipos_ataque (codigo),
   tendencia_mensal (mes); pontes (incidente_id, posicao), únicas por
   construção. Linha inteira repetida: fica uma, e a contagem das que
   saíram aparece na tela. Chave repetida com conteúdo diferente: mostra a
   chave e as linhas, sys.exit(1), nada gravado.
   Por quê: escolher uma em silêncio é decidir sem dizer que decidiu.

6. NULOS
   Nenhuma linha apagada por ter nulo, nenhum nulo preenchido, nenhuma
   anomalia corrigida. Por quê: data_fim nula (381) quer dizer incidente de
   um dia só; dano_real nulo (87) são exatamente os registros de natureza
   policy e report, onde a pergunta "houve dano?" não se aplica — e isso
   não é false, a diferença que raw.incidentes apagou. O que fazer com isso
   é pergunta de mart.

7. SAÍDA NA TELA
   Uma linha por tabela (entra -> sai, duplicatas), as colunas com nulo
   indentadas abaixo, uma linha de total; contagens do banco, milhar com
   ponto, stdout em utf-8. Por quê: é o instrumento de conferência desta
   etapa, e no Prompt de Comando do Windows acento sai embaralhado por
   padrão.

REEXECUÇÃO
   CREATE OR REPLACE dentro de uma única transação: rodar dez vezes = rodar
   uma, e uma falha no meio deixa refined como estava.
   Por quê: metade das tabelas novas e metade velhas parece certo e não é.

ERRO
   Antes de transformar, verifica se as três tabelas de entrada existem em
   raw; faltando alguma, lista quais, manda rodar a ingestão e sai com
   código 1.
"""

import sys

import duckdb

from pipeline.db import conectar, criar_schema

ORIGEM = "raw"
DESTINO = "refined"

# tabela refined -> (tabela raw, chave em nomes refined, [(coluna raw, coluna refined, tipo)])
TABELAS = {
    "incidentes": (
        "incidentes_completo",
        ["incidente_id"],
        [
            ("id", "incidente_id", "texto"),
            ("date", "data", "data"),
            ("date_end", "data_fim", "data"),
            ("date_precision", "precisao_data", "texto"),
            ("month", "mes", "texto"),
            ("title", "titulo", "texto"),
            ("title_zh", "titulo_zh", "texto"),
            ("title_ja", "titulo_ja", "texto"),
            ("title_ko", "titulo_ko", "texto"),
            ("title_de", "titulo_de", "texto"),
            ("title_fr", "titulo_fr", "texto"),
            ("title_es", "titulo_es", "texto"),
            ("kind", "natureza", "texto"),
            ("type", "codigos_ataque", "texto"),
            ("severity", "severidade", "texto"),
            ("confidence", "confianca", "texto"),
            ("real_harm", "dano_real", "booleano"),
            ("ai_involvement", "envolvimento_ia", "texto"),
            ("region", "regioes", "texto"),
            ("disputed", "contestado", "booleano"),
            ("landmark", "marco", "booleano"),
            ("summary", "resumo", "texto"),
            ("summary_zh", "resumo_zh", "texto"),
            ("summary_ja", "resumo_ja", "texto"),
            ("summary_ko", "resumo_ko", "texto"),
            ("summary_de", "resumo_de", "texto"),
            ("summary_fr", "resumo_fr", "texto"),
            ("summary_es", "resumo_es", "texto"),
            ("sources", "urls_fontes", "texto"),
            ("path", "caminho", "texto"),
            ("path_zh", "caminho_zh", "texto"),
        ],
    ),
    "tipos_ataque": (
        "tipos_ataque",
        ["codigo"],
        [
            ("type_code", "codigo", "texto"),
            ("type_name", "nome", "texto"),
            ("incident_count", "qtd_incidentes", "inteiro"),
            ("description", "descricao", "texto"),
        ],
    ),
    "tendencia_mensal": (
        "tendencia_mensal",
        ["mes"],
        [
            ("month", "mes", "texto"),
            ("total_incidents", "total_incidentes", "inteiro"),
            ("critical_incidents", "incidentes_criticos", "inteiro"),
            ("high_severity_incidents", "incidentes_alta", "inteiro"),
            ("medium_severity_incidents", "incidentes_media", "inteiro"),
            ("real_harm_confirmed", "dano_real_confirmado", "inteiro"),
        ],
    ),
}

# ponte -> (coluna multivalor em refined.incidentes, coluna do valor na ponte)
PONTES = {
    "incidente_tipos": ("codigos_ataque", "codigo_ataque"),
    "incidente_regioes": ("regioes", "regiao"),
    "fontes": ("urls_fontes", "url"),
}


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _q(nome: str) -> str:
    return f'"{nome}"'


def _expr(coluna: str, tipo: str) -> str:
    c = _q(coluna)
    if tipo == "data":
        return f"strptime({c}, '%Y-%m-%d')::DATE"
    if tipo == "inteiro":
        return f"CAST({c} AS INTEGER)"
    if tipo == "booleano":
        return (
            f"CASE WHEN {c} IS NULL THEN NULL WHEN {c} = 'true' THEN true "
            f"WHEN {c} = 'false' THEN false "
            f"ELSE error('não é booleano: ''' || {c} || '''') END"
        )
    return c


def _falhar(linhas: list[str]) -> None:
    for linha in linhas:
        print(linha)
    sys.exit(1)


def _verificar_entrada(con: duckdb.DuckDBPyConnection) -> None:
    existentes = {
        nome
        for (nome,) in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name = ?", [ORIGEM]
        ).fetchall()
    }
    faltando = [o for o, _, _ in TABELAS.values() if o not in existentes]
    if faltando:
        _falhar(
            [f"Tabelas faltando no schema {ORIGEM}:"]
            + [f"  {ORIGEM}.{nome}" for nome in faltando]
            + ["Rode a ingestão antes: uv run python -m pipeline.ingestao"]
        )


def _verificar_conversoes(con: duckdb.DuckDBPyConnection) -> None:
    # Coluna por coluna, para que a mensagem diga qual coluna falhou; a
    # mensagem do DuckDB já traz o valor que não converteu.
    for tabela, (origem, _, colunas) in TABELAS.items():
        for bruta, nova, tipo in colunas:
            if tipo == "texto":
                continue
            try:
                con.execute(f"SELECT max({_expr(bruta, tipo)}) FROM {ORIGEM}.{origem}")
            except duckdb.Error as erro:
                _falhar(
                    [
                        (
                            f"Conversão falhou em {DESTINO}.{tabela}.{nova} "
                            f"(de {ORIGEM}.{origem}.{bruta}):"
                        ),
                        f"  {str(erro).splitlines()[0]}",
                    ]
                )

    origem, _, colunas = TABELAS["incidentes"]
    para_bruta = {nova: bruta for bruta, nova, _ in colunas}
    for multivalor, _ in PONTES.values():
        bruta = para_bruta[multivalor]
        vazio = con.execute(
            f"SELECT id, {_q(bruta)} FROM {ORIGEM}.{origem} "
            f"WHERE list_contains(string_split({_q(bruta)}, ';'), '') LIMIT 1"
        ).fetchall()
        if vazio:
            _falhar(
                [
                    (
                        f"Pedaço vazio em {DESTINO}.incidentes.{multivalor} "
                        f"(de {ORIGEM}.{origem}.{bruta}):"
                    ),
                    f"  {vazio[0][0]}: {vazio[0][1]!r}",
                ]
            )


def _verificar_chaves(con: duckdb.DuckDBPyConnection) -> None:
    for origem, chave, colunas in TABELAS.values():
        para_bruta = {nova: bruta for bruta, nova, _ in colunas}
        chave_bruta = ", ".join(_q(para_bruta[c]) for c in chave)
        distintas = f"(SELECT DISTINCT * FROM {ORIGEM}.{origem})"
        conflitos = con.execute(
            f"SELECT * FROM {distintas} WHERE ({chave_bruta}) IN "
            f"(SELECT ({chave_bruta}) FROM {distintas} GROUP BY ALL HAVING count(*) > 1) "
            f"ORDER BY ALL"
        ).fetchall()
        if conflitos:
            _falhar(
                [
                    (
                        f"Chave repetida com conteúdo diferente em {ORIGEM}.{origem} "
                        f"(chave: {', '.join(para_bruta[c] for c in chave)}):"
                    )
                ]
                + [f"  {linha}" for linha in conflitos]
            )


def _gravar(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("BEGIN TRANSACTION")
    try:
        criar_schema(con, DESTINO)
        for tabela, (origem, chave, colunas) in TABELAS.items():
            selecao = ", ".join(f"{_expr(b, t)} AS {_q(n)}" for b, n, t in colunas)
            con.execute(
                f"CREATE OR REPLACE TABLE {DESTINO}.{tabela} AS "
                f"SELECT {selecao} FROM (SELECT DISTINCT * FROM {ORIGEM}.{origem}) "
                f"ORDER BY {', '.join(_q(c) for c in chave)}"
            )
        for ponte, (multivalor, valor) in PONTES.items():
            con.execute(
                f"CREATE OR REPLACE TABLE {DESTINO}.{ponte} AS "
                f"SELECT incidente_id, "
                f"CAST(generate_subscripts(lista, 1) AS INTEGER) AS posicao, "
                f"unnest(lista) AS {_q(valor)} "
                f"FROM (SELECT incidente_id, string_split({_q(multivalor)}, ';') AS lista "
                f"FROM {DESTINO}.incidentes) "
                f"ORDER BY incidente_id, posicao"
            )
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def _contar(con: duckdb.DuckDBPyConnection, schema: str, tabela: str) -> int:
    return con.execute(f"SELECT count(*) FROM {schema}.{tabela}").fetchall()[0][0]


def _nulos(con: duckdb.DuckDBPyConnection, tabela: str) -> list[tuple[str, int]]:
    colunas = [
        nome
        for (nome,) in con.execute(
            "SELECT column_name FROM duckdb_columns() "
            "WHERE schema_name = ? AND table_name = ? ORDER BY column_index",
            [DESTINO, tabela],
        ).fetchall()
    ]
    contagens = con.execute(
        "SELECT "
        + ", ".join(f"count(*) FILTER (WHERE {_q(c)} IS NULL)" for c in colunas)
        + f" FROM {DESTINO}.{tabela}"
    ).fetchall()[0]
    return [(c, n) for c, n in zip(colunas, contagens) if n]


def _imprimir(con: duckdb.DuckDBPyConnection) -> None:
    linhas_saida = []
    for tabela, (origem, _, _) in TABELAS.items():
        entra = _contar(con, ORIGEM, origem)
        distintas = con.execute(
            f"SELECT count(*) FROM (SELECT DISTINCT * FROM {ORIGEM}.{origem})"
        ).fetchall()[0][0]
        linhas_saida.append((tabela, entra, f"  ({_milhar(entra - distintas)} duplicatas)"))
    incidentes = _contar(con, DESTINO, "incidentes")
    for ponte in PONTES:
        linhas_saida.append((ponte, incidentes, ""))

    total = 0
    for tabela, entra, sufixo in linhas_saida:
        sai = _contar(con, DESTINO, tabela)
        total += sai
        nome = f"{DESTINO}.{tabela}"
        print(f"{nome:<27} {_milhar(entra):>5} -> {_milhar(sai):>5} linhas{sufixo}")
        nulos = _nulos(con, tabela)
        if nulos:
            print(
                "    nulos mantidos: "
                + ", ".join(f"{c} {_milhar(n)}" for c, n in nulos)
            )
    print(f"{'total':<36} {_milhar(total):>5} linhas")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        _verificar_entrada(con)
        _verificar_conversoes(con)
        _verificar_chaves(con)
        _gravar(con)
        _imprimir(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
