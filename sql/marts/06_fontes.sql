-- mart.fontes
-- De onde vem a informação — e quanto do dado depende de um domínio só?
-- Gravado como tabela por: uv run python -m pipeline.marts. Spec completa em
-- specs/marts/06_fontes.md.
--
-- FORMA: um único SELECT, lido só de refined; pipeline.marts grava o
-- resultado como tabela. Por quê: a regra de negócio mora inteira aqui.
--
-- GRÃO: um domínio = host da URL, em minúsculas, sem o 'www.' do início.
-- Nada além disso é juntado: www-cdn.anthropic.com fica separado de
-- anthropic.com. Por quê: juntar subdomínios exige saber onde termina o
-- sufixo (.com.cn, .gov.uk), e uma lista mantida à mão erra em silêncio no
-- primeiro sufixo novo. Host sem 'www.' é previsível e nunca junta errado.
-- URL sem host reconhecível vira 'nao_identificado' (hoje nenhuma).
--
-- CONTAGENS lado a lado: citações (linhas de refined.fontes), registros
-- distintos, URLs distintas. registros > urls denuncia compilação: uma URL
-- que serve de fonte para vários registros (o resumo da OWASP cobre 11).
-- qtd_fonte_exclusiva: registros cujas fontes são todas deste domínio —
-- quanto do dado cai se este domínio estiver errado.
--
-- NÃO SE FAZ AQUI: "fonte do próprio fornecedor". O dado não diz de qual
-- empresa é cada incidente, então não há com o que comparar o domínio.

WITH fontes_com_dominio AS (
    SELECT
        f.incidente_id,
        f.posicao,
        f.url,
        coalesce(
            nullif(regexp_replace(lower(regexp_extract(f.url, '^[a-zA-Z]+://([^/:?#]+)', 1)), '^www\.', ''), ''),
            'nao_identificado'
        ) AS dominio
    FROM refined.fontes AS f
),
dominios_por_registro AS (
    SELECT incidente_id, count(DISTINCT dominio) AS n
    FROM fontes_com_dominio
    GROUP BY incidente_id
)
SELECT
    f.dominio,
    CAST(count(*) AS INTEGER) AS qtd_citacoes,
    CAST(count(DISTINCT f.incidente_id) AS INTEGER) AS qtd_registros,
    CAST(count(DISTINCT f.url) AS INTEGER) AS qtd_urls,
    CAST(count(DISTINCT f.incidente_id) FILTER (WHERE i.natureza = 'incident') AS INTEGER) AS qtd_so_incidentes,
    CAST(count(DISTINCT f.incidente_id) FILTER (WHERE f.posicao = 1) AS INTEGER) AS qtd_como_primeira,
    CAST(count(DISTINCT f.incidente_id) FILTER (WHERE d.n = 1) AS INTEGER) AS qtd_fonte_exclusiva
FROM fontes_com_dominio AS f
JOIN refined.incidentes AS i ON i.incidente_id = f.incidente_id
JOIN dominios_por_registro AS d ON d.incidente_id = f.incidente_id
GROUP BY f.dominio
ORDER BY qtd_registros DESC, f.dominio;
