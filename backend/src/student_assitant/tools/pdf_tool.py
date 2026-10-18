from functools import lru_cache

from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.tools import tool
from student_assitant.pdf.pdf_handle import get_docs

# Model đa ngôn ngữ, chạy tốt với tiếng Việt. Đổi model_name nếu muốn model khác.
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


@lru_cache(maxsize=1)
def _get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cpu"},  # đổi "cpu" nếu không có GPU
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def _get_retriever():
    vectorstore = InMemoryVectorStore.from_documents(
        documents=get_docs(),
        embedding=_get_embeddings(),
    )
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 1})


@tool
def retrieve_information(query: str) -> str:
    """Search and return information related to gyn information from the PDF document."""
    retriever = _get_retriever()
    retrieved_docs = retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in retrieved_docs])