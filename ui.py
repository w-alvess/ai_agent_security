"""Explorar o incidentes.duckdb pelo navegador, com a extensão ui do DuckDB.

Executar com:  uv run python ui.py

U1. O QUE FAZ
    Abre o incidentes.duckdb da raiz do projeto, instala e carrega a extensão
    ui (INSTALL ui; LOAD ui;) e chama CALL start_ui(), que sobe o servidor em
    http://localhost:4213 e abre o navegador.
    Por quê: ler tabela no terminal não serve para explorar dado; o navegador
    mostra schemas, colunas e resultados lado a lado.

U2. FICA DE PÉ ATÉ CTRL+C
    A extensão serve enquanto a conexão estiver viva, então o processo fica
    rodando, imprime a URL e "Ctrl+C para encerrar", e no Ctrl+C fecha a
    conexão e sai limpo, sem traceback.
    Por quê: o arquivo .duckdb aceita um único processo escrevendo. Com o
    ui.py de pé, a ingestão falha com um IOException do DuckDB. No Windows
    a mensagem é "Cannot open file ... O arquivo já está sendo usado por
    outro processo", seguida de "File is already open in ... (PID n)", que
    diz qual processo segura o arquivo; em Linux/macOS é "Could not set
    lock on file". Saber exatamente como desligar o servidor faz parte da
    ferramenta.

U3. NÃO CRIA BANCO
    Se incidentes.duckdb não existir, avisa que é preciso rodar a ingestão
    antes e sai com código 1. Por isso não usa conectar() de pipeline/db.py,
    que cria o arquivo quando ele falta.
    Por quê: um banco vazio aberto no navegador parece ingestão quebrada.

U4. SEPARAÇÃO
    Não importa pipeline/ingestao.py, e a ingestão não importa este arquivo.
    Por quê: a ingestão não sobe servidor, não abre navegador e não depende
    da extensão ui para rodar.

U5. SAÍDA NA TELA
    stdout em utf-8. Por quê: no Prompt de Comando do Windows, acento sai
    embaralhado por padrão.
"""

import sys
import time
from pathlib import Path

import duckdb

BANCO = Path(__file__).resolve().parent / "incidentes.duckdb"
URL = "http://localhost:4213"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if not BANCO.is_file():
        print(f"Banco não encontrado: {BANCO}")
        print("Rode a ingestão antes: uv run python -m pipeline.ingestao")
        sys.exit(1)

    con = duckdb.connect(BANCO)
    try:
        con.execute("INSTALL ui; LOAD ui;")
        con.execute("CALL start_ui()")
        print(f"DuckDB UI em {URL}")
        print("Ctrl+C para encerrar")
        # O servidor roda em threads da própria conexão; o processo só precisa
        # continuar vivo, e o sleep é onde o Ctrl+C chega.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrado.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
