"""
TAC - Mesclagem de bancos de dados (versão não-destrutiva)

Diferenças em relação à versão anterior:
  * A mesclagem de parágrafos NÃO depende mais do modified_at do projeto.
    Cada parágrafo é comparado individualmente pelo seu próprio modified_at.
  * Nenhum DELETE é executado. Parágrafos que existem só de um lado são
    preservados, venham eles do banco local ou do remoto.
  * Só colunas presentes nos DOIS bancos são copiadas, o que evita quebra
    quando as máquinas rodam versões diferentes do TAC.
  * O campo "order" é renumerado ao final, de forma determinística, para
    evitar colisões quando as duas máquinas criaram parágrafos em paralelo.
  * O banco remoto é aberto em modo somente-leitura.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class DatabaseMerger:

    def __init__(self, local_db_path):
        self.local_db_path = str(local_db_path)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ts(value):
        """
        Converte o timestamp para datetime com fuso, sempre em UTC.
        Timestamps ingênuos (sem fuso) são interpretados como hora local.
        Valores ausentes ou inválidos viram a data mínima, de modo que
        qualquer registro com data válida vença a comparação.
        """
        if value in (None, ""):
            return _EPOCH
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value))
            except (TypeError, ValueError):
                return _EPOCH
        if dt.tzinfo is None:
            dt = dt.astimezone()          # assume hora local da máquina
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _columns(conn, table):
        return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]

    @staticmethod
    def _insert(cursor, table, row, cols):
        col_sql = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join("?" for _ in cols)
        cursor.execute(
            f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})',
            [row[c] for c in cols],
        )

    @staticmethod
    def _update(cursor, table, row, cols, pk_value, pk="id"):
        updatable = [c for c in cols if c != pk]
        if not updatable:
            return
        set_sql = ", ".join(f'"{c}" = ?' for c in updatable)
        values = [row[c] for c in updatable] + [pk_value]
        cursor.execute(f'UPDATE "{table}" SET {set_sql} WHERE "{pk}" = ?', values)

    # ------------------------------------------------------------------
    # Mesclagem
    # ------------------------------------------------------------------

    def merge(self, remote_db_path):
        """
        Traz para o banco local tudo que existe no banco remoto e não
        se perde nada do que já existia aqui.

        Retorna um dicionário de estatísticas.
        """
        remote_db_path = Path(remote_db_path)
        if not remote_db_path.exists():
            raise FileNotFoundError("Arquivo de banco remoto não encontrado")

        local_conn = sqlite3.connect(self.local_db_path, timeout=30.0)
        remote_conn = sqlite3.connect(
            f"file:{remote_db_path}?mode=ro", uri=True, timeout=30.0
        )
        local_conn.row_factory = sqlite3.Row
        remote_conn.row_factory = sqlite3.Row

        local_conn.execute("PRAGMA foreign_keys = ON;")

        local_cursor = local_conn.cursor()
        remote_cursor = remote_conn.cursor()

        stats = {
            "projects_added": 0,
            "projects_updated": 0,
            "paragraphs_added": 0,
            "paragraphs_updated": 0,
            "paragraphs_processed": 0,
        }

        try:
            proj_cols = [
                c for c in self._columns(remote_conn, "projects")
                if c in self._columns(local_conn, "projects")
            ]
            local_para_cols = self._columns(local_conn, "paragraphs")
            para_cols = [
                c for c in self._columns(remote_conn, "paragraphs")
                if c in local_para_cols
            ]

            # A coluna deleted_at pode faltar se a outra máquina roda uma
            # versão anterior do TAC. Nesse caso a exclusão simplesmente
            # não se propaga, mas nada quebra.
            has_tombstones = "deleted_at" in local_para_cols

            local_cursor.execute("BEGIN IMMEDIATE;")

            remote_cursor.execute("SELECT * FROM projects")
            for r_proj in remote_cursor.fetchall():
                project_id = r_proj["id"]

                local_cursor.execute(
                    "SELECT * FROM projects WHERE id = ?", (project_id,)
                )
                l_proj = local_cursor.fetchone()

                if l_proj is None:
                    self._insert(local_cursor, "projects", r_proj, proj_cols)
                    stats["projects_added"] += 1
                else:
                    # Metadados do projeto (nome, formatação) seguem o mais
                    # recente. Isso NÃO afeta os parágrafos.
                    if self._parse_ts(r_proj["modified_at"]) > self._parse_ts(
                        l_proj["modified_at"]
                    ):
                        self._update(
                            local_cursor, "projects", r_proj, proj_cols, project_id
                        )
                        stats["projects_updated"] += 1

                # ---- parágrafos: união incondicional ----
                touched = self._merge_paragraphs(
                    local_cursor, remote_cursor, project_id, para_cols, stats
                )
                if touched:
                    self._renumber_orders(local_cursor, project_id, has_tombstones)

            local_conn.commit()
            return stats

        except Exception:
            local_conn.rollback()
            raise
        finally:
            local_conn.close()
            remote_conn.close()

    def _merge_paragraphs(self, local_cursor, remote_cursor, project_id, para_cols, stats):
        """Une os parágrafos do projeto. Retorna True se algo mudou."""
        remote_cursor.execute(
            'SELECT * FROM paragraphs WHERE project_id = ? ORDER BY "order" ASC',
            (project_id,),
        )
        remote_paragraphs = remote_cursor.fetchall()
        if not remote_paragraphs:
            return False

        local_cursor.execute(
            "SELECT id, modified_at FROM paragraphs WHERE project_id = ?",
            (project_id,),
        )
        local_index = {row["id"]: row["modified_at"] for row in local_cursor.fetchall()}

        changed = False

        for r_para in remote_paragraphs:
            para_id = r_para["id"]
            stats["paragraphs_processed"] += 1

            if para_id not in local_index:
                # Parágrafo que só existe no remoto: entra sempre.
                self._insert(local_cursor, "paragraphs", r_para, para_cols)
                stats["paragraphs_added"] += 1
                changed = True
                continue

            # Existe dos dois lados: vence a edição mais recente.
            if self._parse_ts(r_para["modified_at"]) > self._parse_ts(
                local_index[para_id]
            ):
                self._update(
                    local_cursor, "paragraphs", r_para, para_cols, para_id
                )
                stats["paragraphs_updated"] += 1
                changed = True

        return changed

    @staticmethod
    def _renumber_orders(local_cursor, project_id, has_tombstones=False):
        """
        Reatribui "order" em sequência (0, 1, 2, ...) resolvendo colisões
        criadas quando as duas máquinas inseriram parágrafos em paralelo.
        O critério de desempate é created_at e depois id, o que produz o
        mesmo resultado nas duas máquinas.

        Parágrafos excluídos (tombstones) ficam de fora da numeração.
        """
        where_deleted = "AND deleted_at IS NULL" if has_tombstones else ""
        local_cursor.execute(
            f'SELECT id FROM paragraphs WHERE project_id = ? {where_deleted} '
            'ORDER BY "order" ASC, created_at ASC, id ASC',
            (project_id,),
        )
        ids = [row["id"] for row in local_cursor.fetchall()]
        local_cursor.executemany(
            'UPDATE paragraphs SET "order" = ? WHERE id = ?',
            [(position, para_id) for position, para_id in enumerate(ids)],
        )