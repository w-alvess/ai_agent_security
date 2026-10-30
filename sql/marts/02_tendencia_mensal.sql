-- mart.tendencia_mensal
-- O problema está crescendo — e o crescimento é de incidentes, de pesquisa
-- ou de regulação?
-- Gravado como tabela por: uv run python -m pipeline.marts. Spec completa em
-- specs/marts/02_tendencia_mensal.md.
--
-- FORMA: um único SELECT, lido só de refined.incidentes; pipeline.marts
-- grava o resultado como tabela. Por quê: a regra de negócio mora aqui.
-- refined.tendencia_mensal não é fonte, é conferência: ela não separa
-- natureza nem marca mês parcial, e bater com ela prova o recálculo.
--
-- GRÃO: um mês ('AAAA-MM'), nada menor. Por quê: 53 incidentes têm o dia
-- inventado (precisao_data 'month' no dia 01, 'part' no dia 15), mas o mês
-- verdadeiro. Incidente com intervalo conta uma vez, no mês de início
-- (coluna mes). Por quê: contar em todo mês atravessado responde "quantos
-- estavam ativos", outra pergunta, e faz a soma passar de 395.
--
-- MESES SEM BURACO: sequência contínua do primeiro ao último mês; mês sem
-- incidente aparece com 0. Por quê: mês que some faz o gráfico ligar os
-- vizinhos e esconder a queda.
--
-- NATUREZA LADO A LADO: total e uma coluna por natureza. Por quê: o mart
-- não decide o que é "incidente"; 2025-10 tem 15 no total e 1 incident.
--
-- CONFERÊNCIA: qtd_criticos, qtd_alta, qtd_media, qtd_dano_confirmado são
-- as colunas de refined.tendencia_mensal recalculadas; batem mês a mês.
-- Contagens, nunca percentuais: o denominador é decisão de quem lê.
--
-- MÊS PARCIAL: true no mês da maior data, se ela não for o último dia do
-- mês. O mês fica na série. Por quê: apagar esconde incidentes; não marcar
-- faz parecer queda. A maior data aproxima o fim da coleta, que o dataset
-- não informa.
--
-- NÃO SE FAZ AQUI: correção do pico de 2026-09 (é fato do dado), média
-- móvel, taxa de crescimento (é cálculo de gráfico).

WITH limites AS (
    SELECT
        CAST(min(mes) || '-01' AS DATE) AS primeiro,
        CAST(max(mes) || '-01' AS DATE) AS ultimo,
        max(data) AS maior_data
    FROM refined.incidentes
),
meses AS (
    SELECT strftime(unnest(generate_series(primeiro, ultimo, INTERVAL 1 MONTH)), '%Y-%m') AS mes
    FROM limites
)
SELECT
    m.mes,
    m.mes = strftime(l.maior_data, '%Y-%m') AND l.maior_data <> last_day(l.maior_data) AS mes_parcial,
    -- count(i.incidente_id) e não count(*): o LEFT JOIN cria uma linha para
    -- mês sem incidente, e count(*) a contaria como 1.
    CAST(count(i.incidente_id) AS INTEGER) AS total,
    CAST(count(i.incidente_id) FILTER (WHERE i.natureza = 'incident') AS INTEGER) AS qtd_incident,
    CAST(count(i.incidente_id) FILTER (WHERE i.natureza = 'research') AS INTEGER) AS qtd_research,
    CAST(count(i.incidente_id) FILTER (WHERE i.natureza = 'policy') AS INTEGER) AS qtd_policy,
    CAST(count(i.incidente_id) FILTER (WHERE i.natureza = 'vulnerability') AS INTEGER) AS qtd_vulnerability,
    CAST(count(i.incidente_id) FILTER (WHERE i.natureza = 'report') AS INTEGER) AS qtd_report,
    CAST(count(i.incidente_id) FILTER (WHERE i.severidade = 'critical') AS INTEGER) AS qtd_criticos,
    CAST(count(i.incidente_id) FILTER (WHERE i.severidade = 'high') AS INTEGER) AS qtd_alta,
    CAST(count(i.incidente_id) FILTER (WHERE i.severidade = 'medium') AS INTEGER) AS qtd_media,
    CAST(count(i.incidente_id) FILTER (WHERE i.dano_real) AS INTEGER) AS qtd_dano_confirmado
FROM meses AS m
CROSS JOIN limites AS l
LEFT JOIN refined.incidentes AS i ON i.mes = m.mes
GROUP BY m.mes, l.maior_data
ORDER BY m.mes;
