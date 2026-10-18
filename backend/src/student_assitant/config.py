"""Cấu hình ứng dụng, đọc từ biến môi trường.

Module này cố ý không import thư viện nặng (langchain, psycopg2...) để test và
import nhanh. File ``.env`` được nạp ở điểm vào (``cli.main``), không nạp ở đây.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


from deepagents.backends.filesystem import FilesystemBackend


from dotenv import load_dotenv  
@dataclass(frozen=True)
class DatabaseSettings:
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str | None = field(default=None, repr=False)  # không lộ ra log/traceback
    name: str = "shop_db"
    statement_timeout_ms: int = 10_000
    max_rows: int = 200
    pool_min: int = 1
    pool_max: int = 5
    sslmode: str = "prefer"  
    def connect_kwargs(self, dbname: str | None = None, *, with_timeout: bool = True) -> dict:
        """Tham số cho ``psycopg2.connect``. Không có password thì để libpq tự tìm
        (PGPASSWORD, ~/.pgpass...)."""
        kwargs: dict = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "dbname": dbname or self.name,
            "sslmode": self.sslmode,
        }
        if self.password:
            kwargs["password"] = self.password
        if with_timeout:
            kwargs["options"] = f"-c statement_timeout={self.statement_timeout_ms}"
        return kwargs



@dataclass(frozen=True)
class Settings:
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    schema_path: Path = Path("sql/schema.sql")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Dựng Settings từ biến môi trường (mặc định ``os.environ``).

        Biến rỗng được coi như chưa đặt. Giá trị số sai định dạng sẽ raise ``ValueError``
        kèm tên biến để dễ sửa.
        """
        env = os.environ if env is None else env
        db_defaults = DatabaseSettings()
        return cls(
            db=DatabaseSettings(
                host=_get(env, "DB_HOST", db_defaults.host),
                port=_get_int(env, "DB_PORT", db_defaults.port),
                user=_get(env, "DB_USER", db_defaults.user),
                password=_get(env, "DB_PASSWORD", "") or None,
                name=_get(env, "DB_NAME", db_defaults.name),
                statement_timeout_ms=_get_int(
                    env, "DB_STATEMENT_TIMEOUT_MS", db_defaults.statement_timeout_ms
                ),
                max_rows=_get_int(env, "DB_MAX_ROWS", db_defaults.max_rows),
                sslmode=_get(env, "DB_SSLMODE", db_defaults.sslmode)
            ),
            schema_path=Path(_get(env, "HOTEL_SCHEMA_PATH", str(cls.schema_path))),
        )


def _get(env: Mapping[str, str], key: str, default: str) -> str:
    return env.get(key, "").strip() or default


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Biến môi trường {key} phải là số nguyên, nhận được {raw!r}") from None

# student_assitant/config.py


# file này: student_assitant/config.py
# parents[0] = student_assitant/  -> ROOT chứa thư mục skills/
ROOT = Path(__file__).resolve().parents[0]

backend = FilesystemBackend(root_dir=str(ROOT), virtual_mode=True)

 # pip install python-dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DB_CONFIG = Settings.from_env().db.connect_kwargs(with_timeout=False)