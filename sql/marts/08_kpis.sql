-- mart.kpis
-- Qual é o tamanho do dado — e quanto dele é incidente, crítico, com dano
-- confirmado, contestado ou apoiado numa fonte só?
-- Gravado como tabela por: uv run python -m pipeline.marts. Spec completa em
-- specs/marts/08_kpis.md.
--
-- FORMA: um único SELECT, lido só de refined; pipeline.marts grava o
-- resultado como tabela. Não lê de outro mart, mesmo com mart.evidencia
-- tendo quase tudo: a ordem dos arquivos fica irrelevante, e bater com
-- evidencia e tendencia_mensal vira conferência, não dependência.
--
-- GRÃO: uma linha só. Por quê: o painel lê cada cartão de uma célula, sem
-- filtrar nem somar (specs/04_painel.md item 2).
--
-- TODAS AS NATUREZAS, salvo qtd_incidentes. Por quê: o painel mostra
-- registros e incidentes lado a lado, e a distância entre os dois é a
-- informação; cortar aqui seria decidir pelo painel o que é "incidente".
-- qtd_fonte_unica segue mart.evidencia: registro sem URL não conta.
--
-- NÃO SE FAZ AQUI: percentual (o denominador é de quem lê), detalhe de dano
-- (está em mart.evidencia), recorte por período (os cartões valem para o
-- período inteiro).

WITH qtd_fontes AS (
    SELECT incidente_id, count(*) AS n
    FROM refined.fontes
    GROUP BY incidente_id
)
SELECT
    CAST(count(*) AS INTEGER) AS qtd_registros,
    CAST(count(*) FILTER (WHERE i.natureza = 'incident') AS INTEGER) AS qtd_incidentes,
    CAST(count(*) FILTER (WHERE i.severidade = 'critical') AS INTEGER) AS qtd_criticos,
    CAST(count(*) FILTER (WHERE i.dano_real) AS INTEGER) AS qtd_dano_confirmado,
    CAST(count(*) FILTER (WHERE i.contestado) AS INTEGER) AS qtd_contestados,
    -- Registro sem nenhuma URL não tem linha em qtd_fontes (n nulo) e fica
    -- fora, como em mart.evidencia.
    CAST(count(*) FILTER (WHERE f.n = 1) AS INTEGER) AS qtd_fonte_unica
FROM refined.incidentes AS i
LEFT JOIN qtd_fontes AS f ON f.incidente_id = i.incidente_id;
