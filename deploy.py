"""Entrada do painel no deploy (Streamlit Community Cloud).

Executar com:  uv run streamlit run deploy.py

D1. O QUE FAZ
    Se incidentes.duckdb não existir, roda o pipeline inteiro, nesta ordem,
    e depois abre app.py sem mudar nada nele:
      scripts/download_data.py
      pipeline.ingestao
      pipeline.transformacao
      pipeline.marts
    Por quê: no servidor não há data/raw/ nem o banco, os dois ficam fora do
    git. Localmente continua valendo app.py, que sem banco mostra o erro e
    não cria arquivo (specs/04_painel.md, item 8).

D2. UMA VEZ POR SERVIDOR
    st.cache_resource: o pipeline roda na primeira visita, e as seguintes
    esperam ou encontram o banco pronto. Falha não fica em cache; a próxima
    visita tenta de novo.
    Por quê: duas visitas gravando ao mesmo tempo esbarram no lock do DuckDB.

D3. CADA ETAPA EM UM PROCESSO
    subprocess com o mesmo Python, nunca import.
    Por quê: as etapas encerram com sys.exit(1) ao falhar, o que derrubaria
    o painel, e a saída delas é o que aparece na tela de erro.

D4. ERRO
    Etapa que falha: st.error com o nome da etapa e a saída dela, e
    st.stop(). As etapas seguintes não rodam e o banco é apagado.
    Por quê: com um banco pela metade, a próxima visita acharia o arquivo e
    não tentaria de novo.
"""

import runpy
import subprocess
import sys
from pathlib import Path

import streamlit as st

import painel

RAIZ = Path(__file__).resolve().parent
ETAPAS = [
    ["scripts/download_data.py"],
    ["-m", "pipeline.ingestao"],
    ["-m", "pipeline.transformacao"],
    ["-m", "pipeline.marts"],
]


@st.cache_resource(show_spinner="Gerando o banco: download e pipeline (cerca de 1 min)…")
def preparar_banco() -> None:
    if painel.BANCO.is_file():
        return
    for etapa in ETAPAS:
        resultado = subprocess.run(
            [sys.executable, *etapa],
            check=False,
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if resultado.returncode != 0:
            painel.BANCO.unlink(missing_ok=True)
            raise RuntimeError(
                f"Falhou: {' '.join(etapa)}\n\n{resultado.stdout}{resultado.stderr}"
            )


try:
    preparar_banco()
except RuntimeError as erro:
    st.error(str(erro))
    st.stop()

runpy.run_path(str(RAIZ / "app.py"), run_name="__main__")
