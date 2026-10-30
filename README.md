# Incidentes de segurança com agentes de IA · 2024-26

Pipeline de dados e painel sobre o dataset público
[AI Agent Security and Real-World Incidents 2024-26](https://www.kaggle.com/datasets/muhammadahmerkhan/ai-agent-security-and-real-world-incidents-2024-26)
do Kaggle: 395 registros de incidentes de segurança envolvendo agentes de IA,
com taxonomia de ataques, série mensal e fontes.

Os dados passam por três camadas em um banco DuckDB local e terminam em um
painel Streamlit:

```
data/raw/*.csv ──► raw ──► refined ──► mart ──► painel (Streamlit)
               ingestão  transformação  marts
```

| Camada    | O que faz                                                                 | Código                                                 |
|-----------|---------------------------------------------------------------------------|--------------------------------------------------------|
| `raw`     | Copia os CSVs como vieram, tudo como texto, sem corrigir nada             | [pipeline/ingestao.py](pipeline/ingestao.py)           |
| `refined` | Tipa as colunas, traduz os nomes e separa listas em tabelas-ponte         | [pipeline/transformacao.py](pipeline/transformacao.py) |
| `mart`    | Uma tabela por arquivo em [sql/marts/](sql/marts/), com a regra de negócio | [pipeline/marts.py](pipeline/marts.py)                 |
| painel    | Só mostra o que os marts já calcularam                                    | [app.py](app.py), [painel.py](painel.py)               |

O projeto é feito com *spec-driven development*: cada etapa e cada mart tem
uma especificação em [specs/](specs/), que é a fonte da verdade, com o porquê
de cada decisão sobre o dado.

## O que não está no repositório

O repositório não traz dados. Os dois itens abaixo ficam no `.gitignore` e são
recriados pelos scripts:

- `data/raw/`, com os CSVs do Kaggle
- `incidentes.duckdb`, o banco gerado pelo pipeline

## Como rodar

Pré-requisitos: [uv](https://docs.astral.sh/uv/getting-started/installation/)
(ele instala o Python 3.14 se precisar).

```bash
# 1. Instalar as dependências
uv sync

# 2. Baixar o dataset do Kaggle para data/raw/
uv run python scripts/download_data.py

# 3. Gerar o banco, nesta ordem
uv run python -m pipeline.ingestao
uv run python -m pipeline.transformacao
uv run python -m pipeline.marts

# 4. Abrir o painel
uv run streamlit run app.py
```

Se o download pedir autenticação, configure suas credenciais do Kaggle
([instruções](https://github.com/Kaggle/kagglehub#authenticate)).

Cada etapa recria suas tabelas do zero, então pode ser rodada de novo quantas
vezes quiser.

### Explorar o banco no navegador

```bash
uv run python ui.py
```

Abre a interface do DuckDB em http://localhost:4213. Encerre com `Ctrl+C`
antes de rodar o pipeline de novo: o arquivo `.duckdb` aceita um único
processo escrevendo.

## Marts

| Tabela                       | Pergunta que responde                                 |
|------------------------------|-------------------------------------------------------|
| `mart.tipos_ataque`          | Quais tipos de ataque aparecem e quantas vezes        |
| `mart.tendencia_mensal`      | Como os registros evoluem mês a mês                   |
| `mart.coocorrencia_ataques`  | Quais tipos de ataque aparecem juntos                 |
| `mart.evidencia`             | Quão sólido é cada registro (confiança, dano, fontes) |
| `mart.regioes`               | Onde os incidentes acontecem                          |
| `mart.fontes`                | De quais domínios vêm as fontes                       |
| `mart.incidentes_painel`     | Lista de registros para o painel filtrar              |
| `mart.kpis`                  | Os totais dos cartões do painel                       |

## Testes

```bash
uv run pytest --cov
uv run ruff check .
```

## Estrutura

```
pipeline/   ingestão, transformação, marts e conexão com o banco
sql/marts/  uma consulta SQL por mart
specs/      especificações de cada etapa e de cada mart
scripts/    download do dataset
test/       testes com pytest
app.py      página do painel (Streamlit)
painel.py   leitura, formatação e gráficos do painel
ui.py       interface web do DuckDB
```
