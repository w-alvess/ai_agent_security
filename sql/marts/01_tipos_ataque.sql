-- mart.tipos_ataque
-- Quais tipos de ataque mais aparecem — e quanto disso é incidente de
-- verdade, crítico, com dano confirmado?
-- Gravado como tabela por: uv run python -m pipeline.marts. Spec completa em
-- specs/marts/01_tipos_ataque.md.
--
-- FORMA: um único SELECT, lido só de refined; pipeline.marts grava o
-- resultado como tabela. Por quê: a regra de negócio mora inteira aqui.
--
-- GRÃO: uma linha por tipo de refined.tipos_ataque (12). LEFT JOIN a partir
-- dos tipos. Por quê: tipo sem incidente aparece com 0; um tipo que some do
-- ranking parece tipo que não existe.
--
-- TRÊS REGRAS DE CONTAGEM, lado a lado. Um incidente pode ter até 3 tipos
-- ('IPI;CRED'), e cada regra responde uma pergunta diferente:
--   qtd_tipo_unico      codigos_ataque é só este código. Regra do
--                       qtd_incidentes original; ignora os 113 incidentes
--                       com mais de um tipo. Soma 282.
--   qtd_tipo_principal  este código em posicao = 1. Um tipo por incidente,
--                       soma 395 e fecha 100%, mas SUPÕE que a ordem é
--                       prioridade, o que o dataset não documenta.
--   qtd_envolvido       este código em qualquer posição. A leitura natural
--                       ("quantos envolvem roubo de credencial?"), mas soma
--                       511 e não fecha 100%.
-- Por quê as três: escolher uma esconderia que CRED vai de 22 a 64.
--
-- NATUREZA: as três contagens incluem todas as naturezas, como o original.
-- qtd_envolvido_so_incidentes repete qtd_envolvido só com
-- natureza = 'incident'. Por quê: GOV lidera com 67, mas só 2 são
-- incidentes; sem essa coluna, o ranking de "ataques" é liderado por leis.
--
-- SEVERIDADE E DANO: contagens sobre a base de qtd_envolvido, nunca
-- percentuais. Por quê: percentual exige escolher denominador, e isso é de
-- quem lê. As quatro colunas de dano somam qtd_envolvido. Nulo em policy
-- ou report é nao_se_aplica (uma lei não tem dano, e isso não é "não houve
-- dano"); nulo em outra natureza é nao_informado, hoje 0. O rótulo vem da
-- natureza, não do nulo, como em mart.evidencia.

SELECT
    t.codigo,
    t.nome,
    CAST(count(p.incidente_id) FILTER (WHERE i.codigos_ataque = t.codigo) AS INTEGER) AS qtd_tipo_unico,
    CAST(count(p.incidente_id) FILTER (WHERE p.posicao = 1) AS INTEGER) AS qtd_tipo_principal,
    CAST(count(p.incidente_id) AS INTEGER) AS qtd_envolvido,
    CAST(count(p.incidente_id) FILTER (WHERE i.natureza = 'incident') AS INTEGER) AS qtd_envolvido_so_incidentes,
    CAST(count(p.incidente_id) FILTER (WHERE i.severidade = 'critical') AS INTEGER) AS qtd_criticos,
    CAST(count(p.incidente_id) FILTER (WHERE i.dano_real) AS INTEGER) AS qtd_dano_confirmado,
    CAST(count(p.incidente_id) FILTER (WHERE NOT i.dano_real) AS INTEGER) AS qtd_dano_negado,
    -- count(p.incidente_id) e não count(*): na linha que o LEFT JOIN cria para
    -- tipo sem incidente, dano_real também é nulo e seria contado aqui.
    CAST(count(p.incidente_id) FILTER (WHERE i.dano_real IS NULL AND i.natureza IN ('policy', 'report')) AS INTEGER) AS qtd_dano_nao_se_aplica,
    CAST(count(p.incidente_id) FILTER (WHERE i.dano_real IS NULL AND i.natureza NOT IN ('policy', 'report')) AS INTEGER) AS qtd_dano_nao_informado
FROM refined.tipos_ataque AS t
LEFT JOIN refined.incidente_tipos AS p ON p.codigo_ataque = t.codigo
LEFT JOIN refined.incidentes AS i ON i.incidente_id = p.incidente_id
GROUP BY t.codigo, t.nome
ORDER BY qtd_envolvido DESC, t.codigo;
