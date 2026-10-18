import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg2
import sqlglot
from psycopg2 import pool, sql
from sqlglot import exp

from student_assitant.config import DatabaseSettings  # chỉnh lại nếu DatabaseSettings nằm nơi khác


class SQLNotAllowedError(Exception):
    pass


class TableNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ForeignKey:
    column: str
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: tuple[tuple[str, str], ...]  # (tên cột, kiểu dữ liệu)
    foreign_keys: tuple[ForeignKey, ...]
    sample_rows: tuple[tuple[Any, ...], ...] | None  # None: không lấy (user không phải admin)
    sample_columns: tuple[str, ...] | None = None  # tên các cột của sample_rows


_FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge,
    exp.Create, exp.Drop, exp.Alter, exp.TruncateTable,
    exp.Command,   # GRANT, COPY, CALL, DO, VACUUM... sqlglot gom vào Command
    exp.Into,      # SELECT ... INTO new_table
)

_FORBIDDEN_FUNCS = {
    "pg_sleep", "pg_terminate_backend", "pg_cancel_backend",
    "lo_import", "lo_export", "set_config", "dblink", "pg_read_file",
    "pg_read_binary_file", "pg_ls_dir",
}

# Cột không bao giờ được trả về (mật khẩu, token...)
_SENSITIVE_COLUMNS = {"password_hash"}

# Giới hạn thời gian chạy cho USER, tránh câu SELECT nặng làm treo database
_USER_STATEMENT_TIMEOUT = "10s"


class Database:
    def __init__(self, db_setting: DatabaseSettings, is_admin: bool = True):
        self.is_admin = is_admin
        self.s = db_setting
        self._pool: pool.ThreadedConnectionPool | None = None
        self._pool_lock = threading.Lock()

    # ---------- Connection pool ----------
    def get_pool(self) -> pool.ThreadedConnectionPool:
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    s = self.s
                    self._pool = pool.ThreadedConnectionPool(
                        s.pool_min, s.pool_max, **s.connect_kwargs()
                    )
        return self._pool

    def close(self) -> None:
        """Đóng toàn bộ connection (gọi khi tắt ứng dụng)."""
        with self._pool_lock:
            if self._pool is not None:
                self._pool.closeall()
                self._pool = None

    @contextmanager
    def get_cur(self) -> Generator[Any, None, None]:
        """Mượn connection, commit nếu thành công, rollback nếu lỗi, luôn trả về pool."""
        # USER không bao giờ được ghi, bất kể tham số truyền vào
        connection_pool = self.get_pool()
        conn = connection_pool.getconn()
        try:
            conn.set_session(autocommit=False)
            with conn.cursor() as cur:
                if not self.is_admin:
                    cur.execute(f"SET LOCAL statement_timeout = '{_USER_STATEMENT_TIMEOUT}'")
                yield cur
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass  # connection hỏng, được xử lý ở finally
            raise
        finally:
            connection_pool.putconn(conn, close=bool(conn.closed))

    # ---------- Kiểm tra SQL ----------
    def sql_script(self, script: str) -> str:
        if self.is_admin:
            return script

        try:
            statements = sqlglot.parse(script, read="postgres")
        except sqlglot.errors.ParseError as e:
            raise SQLNotAllowedError(f"SQL không hợp lệ: {e}") from e

        statements = [s for s in statements if s is not None]
        if len(statements) != 1:
            raise SQLNotAllowedError("Chỉ cho phép đúng 1 câu lệnh.")

        stmt = statements[0]

        if not isinstance(stmt, (exp.Select, exp.Union)):
            raise SQLNotAllowedError("Chỉ cho phép câu lệnh SELECT.")

        for node in stmt.walk():
            if isinstance(node, _FORBIDDEN):
                raise SQLNotAllowedError(f"Không cho phép: {type(node).__name__}")

            if isinstance(node, (exp.Anonymous, exp.Func)):
                name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()) or ""
                if name.lower() in _FORBIDDEN_FUNCS:
                    raise SQLNotAllowedError(f"Không cho phép hàm: {name}")

            if isinstance(node, exp.Column) and node.name.lower() in _SENSITIVE_COLUMNS:
                raise SQLNotAllowedError(f"Không cho phép cột: {node.name}")

        # SELECT * sẽ kéo theo cả cột nhạy cảm (password_hash)
        for select in stmt.find_all(exp.Select):
            for proj in select.expressions:
                if isinstance(proj, exp.Star) or (
                    isinstance(proj, exp.Column) and isinstance(proj.this, exp.Star)
                ):
                    raise SQLNotAllowedError(
                        "SQL không hợp lệ: không dùng SELECT *, hãy liệt kê cột cần lấy."
                    )

        return script

    # ---------- Schema ----------
    def list_tables(self) -> list[str]:
        with self.get_cur() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
                """
            )
            return [row[0] for row in cur.fetchall()]

    def describe_table(
        self,
        table_name: str,
        *,
        schema: str = "public",
        sample_limit: int = 3,
    ) -> TableInfo:
        """Trả về cột, khóa ngoại và (nếu là admin) vài dòng mẫu của một bảng."""
        with self.get_cur() as cur:
            # 1. Cột + kiểu dữ liệu
            cur.execute(
                """
                select column_name, data_type
                from information_schema.columns
                where table_schema = %s and table_name = %s
                order by ordinal_position
                """,
                (schema, table_name),
            )
            columns = tuple((r[0], r[1]) for r in cur.fetchall())
            if not columns:
                raise TableNotFoundError(f"Không tìm thấy bảng '{schema}.{table_name}'")

            # 2. Khóa ngoại (dùng pg_constraint để đúng với khóa ngoại nhiều cột)
            cur.execute(
                """
                select
                    a.attname  as column_name,
                    cf.relname as ref_table,
                    af.attname as ref_column
                from pg_constraint con
                join pg_class c       on c.oid = con.conrelid
                join pg_namespace n   on n.oid = c.relnamespace
                join pg_class cf      on cf.oid = con.confrelid
                join lateral unnest(con.conkey, con.confkey) as k(attnum, fattnum) on true
                join pg_attribute a   on a.attrelid = con.conrelid  and a.attnum  = k.attnum
                join pg_attribute af  on af.attrelid = con.confrelid and af.attnum = k.fattnum
                where con.contype = 'f'
                  and n.nspname = %s
                  and c.relname = %s
                order by a.attnum
                """,
                (schema, table_name),
            )
            foreign_keys = tuple(ForeignKey(r[0], r[1], r[2]) for r in cur.fetchall())

            # 3. Dòng mẫu: chỉ admin, và bỏ các cột nhạy cảm
            sample_rows: tuple[tuple[Any, ...], ...] | None = None
            sample_columns: tuple[str, ...] | None = None
            if self.is_admin:
                safe_cols = tuple(c for c, _ in columns if c.lower() not in _SENSITIVE_COLUMNS)
                if safe_cols:
                    cur.execute(
                        sql.SQL("select {} from {}.{} limit %s").format(
                            sql.SQL(", ").join(sql.Identifier(c) for c in safe_cols),
                            sql.Identifier(schema),
                            sql.Identifier(table_name),
                        ),
                        (sample_limit,),
                    )
                    sample_rows = tuple(tuple(r) for r in cur.fetchall())
                    sample_columns = safe_cols

        return TableInfo(
            name=table_name,
            columns=columns,
            foreign_keys=foreign_keys,
            sample_rows=sample_rows,
            sample_columns=sample_columns,
        )

    # ---------- Thực thi ----------
    def run(self, script: str) -> list[tuple[Any, ...]]:
        """Chạy script SQL.
        - Câu trả về dữ liệu (SELECT, hoặc ... RETURNING): trả danh sách các dòng.
        - Câu ghi không trả dữ liệu (INSERT/UPDATE/DELETE): trả [(số_dòng_bị_ảnh_hưởng,)]."""
        script = self.sql_script(script)
        with self.get_cur() as cur:
            cur.execute(script)
            if cur.description is None:
                return [(cur.rowcount,)]
            return cur.fetchall()