import os
from functools import lru_cache
from pathlib import Path

from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Gốc project (thư mục "copy"), tính từ vị trí file này
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PDF_PATH = PROJECT_ROOT / "data" / "GymHeart_Fitness_Thong_Tin.pdf"


def _pdf_path() -> Path:
    # Có thể ghi đè bằng PDF_PATH trong .env, không có thì dùng đường dẫn mặc định
    return Path(os.environ.get("PDF_PATH") or DEFAULT_PDF_PATH)


@lru_cache(maxsize=1)
def get_docs():
    path = _pdf_path()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {path}")
    loader = PDFPlumberLoader(str(path))
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=750, chunk_overlap = 200)  # giữ nguyên dòng cũ của bạn
    return splitter.split_documents(docs)