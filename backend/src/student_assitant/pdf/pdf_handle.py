import os
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Gốc project (thư mục "copy"), tính từ vị trí file này
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "thong_tin_phong_gym.txt"

# Dòng ngăn cách giữa các mục trong file txt
SECTION_SEPARATOR = "\n---\n"


def _data_path() -> Path:
    # Có thể ghi đè bằng DATA_PATH trong .env, không có thì dùng đường dẫn mặc định
    return Path(os.environ.get("DATA_PATH") or DEFAULT_DATA_PATH)


@lru_cache(maxsize=1)
def get_docs():
    path = _data_path()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {path}")

    text = path.read_text(encoding="utf-8")

    # Tách theo từng mục (mỗi mục là 1 chunk tự đủ nghĩa)
    sections = [s.strip() for s in text.split(SECTION_SEPARATOR) if s.strip()]
    docs = [
        Document(page_content=s, metadata={"source": path.name, "section": i})
        for i, s in enumerate(sections)
    ]

    # Chỉ cắt thêm nếu một mục dài hơn chunk_size
    splitter = RecursiveCharacterTextSplitter(chunk_size=750, chunk_overlap=200)  # giữ nguyên dòng cũ của bạn
    return splitter.split_documents(docs)