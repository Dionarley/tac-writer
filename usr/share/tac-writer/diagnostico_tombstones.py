#!/usr/bin/env python3
"""
Compara os tombstones do banco local com os do arquivo que está na nuvem.

Rodar NO PC PRINCIPAL, logo depois de sincronizar:

  1. Baixe tac_writer.db do site do Dropbox para ~/Downloads
  2. python3 diagnostico_tombstones.py ~/Downloads/tac_writer.db

Não altera nada.
"""

import sqlite3
import sys
from pathlib import Path

LOCAL_DB = Path.home() / ".local/share/tac/projects.db"


def abrir(caminho):
    conn = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def resumo(conn, rotulo):
    cols = [r[1] for r in conn.execute('PRAGMA table_info("paragraphs")')]
    tem = "deleted_at" in cols
    print(f"--- {rotulo} ---")
    print(f"  coluna deleted_at: {'sim' if tem else 'NÃO'}")

    total = conn.execute("SELECT COUNT(*) FROM paragraphs").fetchone()[0]
    print(f"  parágrafos no total: {total}")

    if not tem:
        print()
        return None

    linhas = conn.execute("""
        SELECT p.project_id, pr.name, COUNT(*) AS n
        FROM paragraphs p
        LEFT JOIN projects pr ON pr.id = p.project_id
        WHERE p.deleted_at IS NOT NULL
        GROUP BY p.project_id
    """).fetchall()

    total_tomb = sum(r["n"] for r in linhas)
    print(f"  tombstones: {total_tomb}")
    for r in linhas:
        print(f"    {r['n']:3}  em '{r['name'] or '(projeto ausente)'}'")

    ids = {r[0] for r in conn.execute(
        "SELECT id FROM paragraphs WHERE deleted_at IS NOT NULL")}
    print()
    return ids


if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

remoto_path = Path(sys.argv[1]).expanduser()
if not remoto_path.exists():
    print(f"Arquivo não encontrado: {remoto_path}")
    sys.exit(1)

local_ids = resumo(abrir(LOCAL_DB), "BANCO LOCAL (este computador)")
remoto_ids = resumo(abrir(remoto_path), "ARQUIVO DA NUVEM")

print("=" * 60)

if local_ids is None:
    print("O banco local não tem a coluna. A migração não rodou aqui.")
elif remoto_ids is None:
    print("O arquivo da nuvem não tem a coluna: ele foi enviado por uma")
    print("máquina desatualizada e o upload deste computador não o")
    print("sobrescreveu. Sincronize aqui e baixe o arquivo de novo.")
elif local_ids and not remoto_ids:
    print(f"Os {len(local_ids)} tombstones existem aqui mas NÃO chegaram à")
    print("nuvem. O upload do _perform_sync não está levando o estado atual")
    print("do banco — investigar o trecho do snapshot.")
elif local_ids - remoto_ids:
    faltam = local_ids - remoto_ids
    print(f"{len(faltam)} tombstone(s) existem aqui e faltam na nuvem:")
    for i in list(faltam)[:10]:
        print(f"  {i}")
elif not local_ids:
    print("Não há tombstone nenhum aqui. As exclusões não foram gravadas,")
    print("ou foram destruídas depois. Exclua um parágrafo de teste e")
    print("rode este script de novo para ver se o tombstone aparece.")
else:
    print("Os tombstones locais estão todos na nuvem. Se o outro computador")
    print("ainda ressuscita parágrafos, o problema está no merge dele.")
