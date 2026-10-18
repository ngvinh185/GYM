import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()
HOST = os.environ.get("DB_HOST", "localhost")
USER = os.environ.get("DB_USER", "postgres")
PASSWORD = os.environ.get("DB_PASSWORD")
PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_DATABASE", "gym_db")


def create_database():
    conn = psycopg2.connect(host=HOST, user=USER, password=PASSWORD, port=PORT, database="postgres")
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            if cur.fetchone():
                print(f"Database '{DB_NAME}' đã tồn tại, bỏ qua bước tạo.")
                return
            # Không thể dùng %s cho tên database -> dùng psycopg2.sql.Identifier để tránh injection
            from psycopg2 import sql
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
            print(f"Đã tạo database '{DB_NAME}'.")
    finally:
        conn.close()


def run_schema():
    conn = psycopg2.connect(host=HOST, user=USER, password=PASSWORD, port=PORT, database=DB_NAME)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            with open("database_setup.sql", "r", encoding="utf-8") as f:
                cur.execute(f.read())
        print("Đã tạo bảng + insert dữ liệu mẫu thành công!")
    except Exception as e:
        print(f"Lỗi khi chạy schema: {type(e).__name__}: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    create_database()
    run_schema()