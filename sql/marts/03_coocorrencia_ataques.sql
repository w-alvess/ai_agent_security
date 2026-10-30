-- mart.coocorrencia_ataques
-- Quais tipos de ataque aparecem juntos no mesmo incidente — e isso
-- acontece em incidentes de verdade ou só em pesquisa?
-- Gravado como tabela por: uv run python -m pipeline.marts. Spec completa em
-- specs/marts/03_coocorrencia_ataques.md.
--
-- FORMA: um único SELECT, lido só de refined; pipeline.marts grava o
-- resultado como tabela. Não ler de outro mart deixa a ordem dos arquivos
-- irrelevante.
--
-- PAR SEM ORDEM: {A, B} com A < B por código. Por quê: a ordem em
-- codigos_ataque não é documentada como prioridade; par ordenado afirmaria
-- "IPI leva a EXFIL", e o dado não diz isso.
--
-- GRÃO: os 66 pares possíveis entre os 12 tipos, inclusive com 0. Por quê:
-- num mapa de calor, "nunca aparecem juntos" é informação (OTHER nunca se
-- combina). Incidente com 3 tipos gera 3 pares: cada um coocorreu de fato,
-- e não há critério para escolher um. Por isso a soma (119) passa dos 113
-- incidentes com mais de um tipo.
--
-- qtd_juntos_so_incidentes: EXFIL+IPI lidera com 24, mas só 3 são
-- incidentes; sem a coluna, o par que lidera é o de pesquisa.
-- qtd_envolvido_a/b: a base de cada tipo, para ler 24 em proporção.
-- Contagens, nunca percentual: qual base é o denominador é de quem lê.

WITH pares_possiveis AS (
    SELECT a.codigo AS codigo_a, a.nome AS nome_a, b.codigo AS codigo_b, b.nome AS nome_b
    FROM refined.tipos_ataque AS a
    JOIN refined.tipos_ataque AS b ON a.codigo < b.codigo
),
-- A condição a < b gera cada par uma vez por incidente, já sem ordem.
pares_observados AS (
    SELECT a.incidente_id, a.codigo_ataque AS codigo_a, b.codigo_ataque AS codigo_b
    FROM refined.incidente_tipos AS a
    JOIN refined.incidente_tipos AS b
        ON b.incidente_id = a.incidente_id AND a.codigo_ataque < b.codigo_ataque
),
envolvidos AS (
    SELECT codigo_ataque AS codigo, count(*) AS qtd
    FROM refined.incidente_tipos
    GROUP BY codigo_ataque
)
SELECT
    p.codigo_a,
    p.nome_a,
    p.codigo_b,
    p.nome_b,
    CAST(count(o.incidente_id) AS INTEGER) AS qtd_juntos,
    CAST(count(o.incidente_id) FILTER (WHERE i.natureza = 'incident') AS INTEGER) AS qtd_juntos_so_incidentes,
    CAST(coalesce(any_value(ea.qtd), 0) AS INTEGER) AS qtd_envolvido_a,
    CAST(coalesce(any_value(eb.qtd), 0) AS INTEGER) AS qtd_envolvido_b
FROM pares_possiveis AS p
LEFT JOIN pares_observados AS o ON o.codigo_a = p.codigo_a AND o.codigo_b = p.codigo_b
LEFT JOIN refined.incidentes AS i ON i.incidente_id = o.incidente_id
-- coalesce: tipo sem nenhum incidente não tem linha em envolvidos; a base
-- dele é 0, não desconhecida.
LEFT JOIN envolvidos AS ea ON ea.codigo = p.codigo_a
LEFT JOIN envolvidos AS eb ON eb.codigo = p.codigo_b
GROUP BY p.codigo_a, p.nome_a, p.codigo_b, p.nome_b
ORDER BY qtd_juntos DESC, p.codigo_a, p.codigo_b;
