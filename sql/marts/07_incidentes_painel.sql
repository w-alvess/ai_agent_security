-- mart.incidentes_painel
-- Uma linha por registro, pronta para o painel filtrar e listar.
-- Gravado como tabela por: uv run python -m pipeline.marts. Spec completa em
-- specs/marts/07_incidentes_painel.md.
--
-- FORMA: um único SELECT, lido só de refined; pipeline.marts grava o
-- resultado como tabela. Por quê: a regra de negócio mora inteira aqui.
--
-- GRÃO: os 395 registros, todas as naturezas. Por quê: o painel filtra por
-- natureza; cortar aqui seria decidir pelo painel o que é "incidente".
--
-- LISTAS, não strings com ';': codigos_ataque, nomes_ataque, regioes e
-- urls_fontes viram LIST na ordem de posicao. Por quê: o filtro do painel é
-- "registros que envolvem X" (list_contains), a regra qtd_envolvido de
-- mart.tipos_ataque. Não há coluna de tipo principal: ela supõe que a
-- ordem é prioridade, e o dataset não documenta isso.
--
-- situacao_dano: a mesma regra de mart.evidencia — nulo em policy/report é
-- nao_se_aplica, nulo em outra natureza é nao_informado.
--
-- Só o texto em inglês (titulo, resumo). Por quê: o painel é em uma língua;
-- as traduções continuam em refined.incidentes para quem precisar.

WITH tipos AS (
    SELECT
        p.incidente_id,
        list(p.codigo_ataque ORDER BY p.posicao) AS codigos_ataque,
        -- Código sem nome em tipos_ataque vira NULL dentro da lista, na
        -- mesma posição: aparece, em vez de sumir.
        list(t.nome ORDER BY p.posicao) AS nomes_ataque
    FROM refined.incidente_tipos AS p
    LEFT JOIN refined.tipos_ataque AS t ON t.codigo = p.codigo_ataque
    GROUP BY p.incidente_id
),
regioes AS (
    SELECT incidente_id, list(regiao ORDER BY posicao) AS regioes
    FROM refined.incidente_regioes
    GROUP BY incidente_id
),
fontes AS (
    SELECT incidente_id, list(url ORDER BY posicao) AS urls_fontes
    FROM refined.fontes
    GROUP BY incidente_id
)
SELECT
    i.incidente_id,
    i.data,
    i.precisao_data,
    i.data_fim,
    i.mes,
    i.titulo,
    i.resumo,
    i.natureza,
    i.severidade,
    i.confianca,
    i.envolvimento_ia,
    i.contestado,
    i.marco,
    CASE
        WHEN i.dano_real THEN 'confirmado'
        WHEN NOT i.dano_real THEN 'negado'
        WHEN i.natureza IN ('policy', 'report') THEN 'nao_se_aplica'
        ELSE 'nao_informado'
    END AS situacao_dano,
    t.codigos_ataque,
    t.nomes_ataque,
    r.regioes,
    f.urls_fontes,
    CAST(len(f.urls_fontes) AS INTEGER) AS qtd_fontes
FROM refined.incidentes AS i
LEFT JOIN tipos AS t ON t.incidente_id = i.incidente_id
LEFT JOIN regioes AS r ON r.incidente_id = i.incidente_id
LEFT JOIN fontes AS f ON f.incidente_id = i.incidente_id
ORDER BY i.data DESC, i.incidente_id;
