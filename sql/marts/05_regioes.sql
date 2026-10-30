-- mart.regioes
-- Onde acontece — e quanto do dado permite responder isso?
-- Gravado como tabela por: uv run python -m pipeline.marts. Spec completa em
-- specs/marts/05_regioes.md.
--
-- FORMA: um único SELECT, lido só de refined; pipeline.marts grava o
-- resultado como tabela. Por quê: a regra de negócio mora inteira aqui.
--
-- GRÃO: uma linha por região que aparece no dado. Por quê: a fonte não tem
-- tabela de regiões, então não há lista de "possíveis" para mostrar com 0.
--
-- GLOBAL FICA, com escopo declarado (global / regional / local). Por quê:
-- tirá-lo apagaria 310 registros; mantê-lo sem marca põe GLOBAL e US na
-- mesma escala num mapa. "local" e não "país": o mart não decide se HK ou
-- TW são países. Nenhum código é fundido em outro (HK não vira CN).
-- Código fora das três listas é nao_classificado: um código novo na fonte
-- não vira local em silêncio.
--
-- CONTAGENS lado a lado, como em mart.tipos_ataque: envolvido (qualquer
-- posição, soma 409) e região única. qtd_com_global separa 'CN;GLOBAL'
-- (origem chinesa, alcance global) de um caso só na China.
--
-- LIMITE: fora de GLOBAL, só US e CN passam de 9 registros.

SELECT
    r.regiao,
    CASE
        WHEN r.regiao = 'GLOBAL' THEN 'global'
        WHEN r.regiao IN ('EU', 'LATAM', 'SEA', 'APAC') THEN 'regional'
        WHEN r.regiao IN ('US', 'CN', 'JP', 'KR', 'AU', 'TW', 'UK', 'HK') THEN 'local'
        ELSE 'nao_classificado'
    END AS escopo,
    CAST(count(*) AS INTEGER) AS qtd_envolvido,
    CAST(count(*) FILTER (WHERE i.regioes = r.regiao) AS INTEGER) AS qtd_regiao_unica,
    -- list_contains e não LIKE '%GLOBAL%': compara o código inteiro, não um
    -- pedaço de texto.
    CAST(count(*) FILTER (
        WHERE r.regiao <> 'GLOBAL' AND list_contains(string_split(i.regioes, ';'), 'GLOBAL')
    ) AS INTEGER) AS qtd_com_global,
    CAST(count(*) FILTER (WHERE i.natureza = 'incident') AS INTEGER) AS qtd_envolvido_so_incidentes,
    CAST(count(*) FILTER (WHERE i.severidade = 'critical') AS INTEGER) AS qtd_criticos,
    CAST(count(*) FILTER (WHERE i.dano_real) AS INTEGER) AS qtd_dano_confirmado
FROM refined.incidente_regioes AS r
JOIN refined.incidentes AS i ON i.incidente_id = r.incidente_id
GROUP BY r.regiao
ORDER BY qtd_envolvido DESC, r.regiao;
