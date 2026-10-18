from student_assitant.database.database import Database, TableInfo
from langchain.tools import tool
from langchain_core.tools import BaseTool
import psycopg2
from student_assitant.database.database import (
    Database, SQLNotAllowedError, TableInfo, TableNotFoundError,
)
from typing import Any
def format_table_info(info: TableInfo) -> str:
  """Định dạng schema một bảng. Dòng mẫu chỉ có khi ``info.sample_rows`` không phải None."""
  col_info = ", ".join(f"{name} ({dtype})" for name, dtype in info.columns)
  if info.foreign_keys:
      fk_info = "\n".join(
          f"  - Bảng {info.name} có cột {fk.column} liên kết vào bảng "
          f"{fk.ref_table} với cột {fk.ref_column} thông qua khóa ngoại"
          for fk in info.foreign_keys
      )
  else:
      fk_info = "  - Không có khóa ngoại"

  text = f"Table {info.name}:\nColumns: {col_info}\nForeign Keys:\n{fk_info}"
  if info.sample_rows is not None:
      text += f"\nSample rows: {list(info.sample_rows)}"
  return text


def get_sql_tool(db: Database) -> list[BaseTool]:
  
  @tool
  def get_list_table() -> list[str]:
    """Lấy danh sách tên bảng trong cơ sở dữ liệu."""
    return db.list_tables()
  
  @tool
  def get_schema_table(table: str) -> str:
      """Lấy schema của một bảng (cột, kiểu, khóa ngoại, dòng mẫu nếu là admin)."""
      try:
          return format_table_info(db.describe_table(table))
      except TableNotFoundError as e:
          return f"Lỗi: {e}"

  @tool
  def run_sql(script: str) -> Any:
      """Chạy một câu SQL và trả về các dòng kết quả."""
      try:
          return db.run(script)
      except SQLNotAllowedError as e:
          return str(e)  # giữ nguyên "Chỉ cho phép..." để agent nhận ra bị chặn quyền
      except psycopg2.Error as e:
          return f"Lỗi database: {(e.pgerror or str(e)).strip()}"
      
  return [get_list_table, get_schema_table, run_sql]
  

  
  
