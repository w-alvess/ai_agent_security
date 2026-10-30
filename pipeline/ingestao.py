"""Ingestão: copia os CSVs de data/raw/ para o schema raw, sem decidir nada.

Executar com:  uv run python -m pipeline.ingestao

1. ESCOPO E NOMES
   Schema de destino: raw. Mapa arquivo -> tabela em ARQUIVOS, completo e
   literal. Os nomes das tabelas vão para o português porque é o vocabulário
   digitado de memória nos JOINs das próximas etapas; os nomes das colunas
   ficam como vieram.
   sources_bibliography.txt fica em data/raw/, mas não é ingerido nem
   verificado. Por quê: as 724 URLs dele são exatamente as da coluna sources
   de ai_agent_incidents_full.csv, sem dizer a que incidente cada uma
   pertence. Se o dashboard precisar de fontes, elas saem da coluna sources
   na etapa refined, mantendo a ligação com o incidente.

2. PROIBIÇÕES (a regra central desta etapa)
   Nenhuma conversão de tipo, nenhuma linha descartada ou deduplicada,
   nenhum nome de coluna alterado, nenhum valor corrigido, preenchido ou
   normalizado. incidentes e incidentes_completo entram as duas, mesmo
   descrevendo os mesmos incidentes; colunas traduzidas entram como estão.
   Por quê: a fronteira entre "o dado que chegou" e "o dado que eu decidi"
   é a passagem de raw para refined, na etapa 2. Corrigir aqui apaga essa
   fronteira.

3. REEXECUÇÃO
   Cada tabela é recriada (CREATE OR REPLACE), nunca acrescentada: rodar dez
   vezes dá o mesmo resultado que rodar uma. Por quê: é o que permite errar
   sem medo.

4. LEITURA DOS ARQUIVOS
   encoding utf-8 declarado, nunca adivinhado. Por quê: há texto em chinês,
   japonês e coreano, e adivinhar o encoding corrompe essas colunas sem erro.
   Só campo vazio vira nulo; "NA", "None" ou "null" continuam texto.
   Por quê: o padrão do pandas transforma "NA" em nulo, e "NA" é também a
   sigla de América do Norte numa coluna de região.

5. TIPAGEM
   Toda coluna entra como texto (dtype=str), inferência desligada.
   Por quê: a inferência leria year, month e incident_count como número, e
   "2024-12" poderia virar data. A conversão acontece na etapa 2, onde é uma
   decisão registrada.

6. SAÍDA NA TELA
   Uma linha por tabela, na ordem do mapa, com nome qualificado e contagem
   vinda do banco, milhar separado por ponto; uma linha final com o total.
   Por quê: essa saída é o único instrumento de conferência desta etapa.
   stdout em utf-8. Por quê: no Prompt de Comando do Windows, acento sai
   embaralhado por padrão.

7. ERRO
   Antes de abrir o banco, verifica se os quatro .csv existem. Faltando
   algum: lista os que faltam, a pasta onde procurou, como baixá-los, e sai
   com código 1, sem ingerir nada.
   Por quê: ingerir três de quatro tabelas em silêncio produz um dashboard
   errado que parece certo.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

SCHEMA = "raw"

ARQUIVOS = {
    "ai_agent_incidents_clean.csv": "incidentes",
    "ai_agent_incidents_full.csv": "incidentes_completo",
    "taxonomy_attack_types.csv": "tipos_ataque",
    "monthly_incident_trends.csv": "tendencia_mensal",
}


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    faltando = [nome for nome in ARQUIVOS if not (PASTA_RAW / nome).is_file()]
    if faltando:
        print(f"Arquivos faltando em {PASTA_RAW}:")
        for nome in faltando:
            print(f"  {nome}")
        print("Baixe com: uv run python scripts/download_data.py")
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, SCHEMA)
        total = 0
        for arquivo, tabela in ARQUIVOS.items():
            df = pd.read_csv(
                PASTA_RAW / arquivo,
                dtype=str,
                encoding="utf-8",
                keep_default_na=False,
                na_values=[""],
            )
            linhas = gravar(con, df, SCHEMA, tabela)
            total += linhas
            print(f"{SCHEMA}.{tabela:<22} {_milhar(linhas):>7}")
        print(f"{'total':<26} {_milhar(total):>7}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
