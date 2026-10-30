-- mart.evidencia
-- Quanto disso é confirmado — e a resposta muda conforme o tipo de registro?
-- Gravado como tabela por: uv run python -m pipeline.marts. Spec completa em
-- specs/marts/04_evidencia.md.
--
-- FORMA: um único SELECT, lido só de refined; pipeline.marts grava o
-- resultado como tabela. Por quê: a regra de negócio mora inteira aqui.
--
-- GRÃO: uma linha por natureza. Por quê: os sinais significam coisas
-- diferentes em cada uma — dano não existe numa lei, incidente sem dano é
-- quase-acidente, pesquisa sem dano é o esperado.
--
-- DANO EM QUATRO: confirmado, negado, nao_se_aplica (nulo em policy ou
-- report) e nao_informado (nulo em qualquer outra natureza, hoje 0).
-- Por quê: lei e relatório não têm dano. O rótulo vem da natureza, não do
-- nulo: um incidente com dano nulo cai em nao_informado e aparece, em vez
-- de virar "não se aplica" só por ser nulo.
--
-- OUTROS SINAIS lado a lado: confiança A-D, envolvimento de IA, contestado,
-- fonte única ou várias. Cada grupo soma total. Contagens, nunca
-- percentual, e nenhum índice composto: o peso de cada sinal é de quem lê.
-- contestado e envolvimento_ia ficam separados: 8 contestados têm IA
-- 'confirmed', ou seja, o que se contesta é outra parte do fato.

WITH qtd_fontes AS (
    SELECT incidente_id, count(*) AS n
    FROM refined.fontes
    GROUP BY incidente_id
)
SELECT
    i.natureza,
    CAST(count(*) AS INTEGER) AS total,
    CAST(count(*) FILTER (WHERE i.confianca = 'A') AS INTEGER) AS qtd_confianca_a,
    CAST(count(*) FILTER (WHERE i.confianca = 'B') AS INTEGER) AS qtd_confianca_b,
    CAST(count(*) FILTER (WHERE i.confianca = 'C') AS INTEGER) AS qtd_confianca_c,
    CAST(count(*) FILTER (WHERE i.confianca = 'D') AS INTEGER) AS qtd_confianca_d,
    CAST(count(*) FILTER (WHERE i.envolvimento_ia = 'confirmed') AS INTEGER) AS qtd_ia_confirmada,
    CAST(count(*) FILTER (WHERE i.envolvimento_ia = 'disputed') AS INTEGER) AS qtd_ia_contestada,
    CAST(count(*) FILTER (WHERE i.envolvimento_ia = 'unverified') AS INTEGER) AS qtd_ia_nao_verificada,
    CAST(count(*) FILTER (WHERE i.envolvimento_ia = 'not-applicable') AS INTEGER) AS qtd_ia_nao_se_aplica,
    CAST(count(*) FILTER (WHERE i.contestado) AS INTEGER) AS qtd_contestado,
    CAST(count(*) FILTER (WHERE i.dano_real) AS INTEGER) AS qtd_dano_confirmado,
    CAST(count(*) FILTER (WHERE NOT i.dano_real) AS INTEGER) AS qtd_dano_negado,
    CAST(count(*) FILTER (WHERE i.dano_real IS NULL AND i.natureza IN ('policy', 'report')) AS INTEGER) AS qtd_dano_nao_se_aplica,
    CAST(count(*) FILTER (WHERE i.dano_real IS NULL AND i.natureza NOT IN ('policy', 'report')) AS INTEGER) AS qtd_dano_nao_informado,
    -- Incidente sem nenhuma URL não tem linha em qtd_fontes (n nulo) e não
    -- entra em nenhuma das duas; o critério "fontes somam total" acusa.
    CAST(count(*) FILTER (WHERE f.n = 1) AS INTEGER) AS qtd_fonte_unica,
    CAST(count(*) FILTER (WHERE f.n > 1) AS INTEGER) AS qtd_varias_fontes
FROM refined.incidentes AS i
LEFT JOIN qtd_fontes AS f ON f.incidente_id = i.incidente_id
GROUP BY i.natureza
ORDER BY total DESC, i.natureza;
