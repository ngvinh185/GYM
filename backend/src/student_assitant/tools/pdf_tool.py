from functools import lru_cache

from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain.tools import tool
from student_assitant.pdf.pdf_handle import get_docs

# Model embedding của OpenAI. Đổi sang "text-embedding-3-large" nếu muốn chính xác hơn.
EMBEDDING_MODEL_NAME = "text-embedding-3-small"


@lru_cache(maxsize=1)
def _get_embeddings():
    # API key lấy từ biến môi trường OPENAI_API_KEY (file .env)
    return OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def _get_retriever():
    vectorstore = InMemoryVectorStore.from_documents(
        documents=get_docs(),
        embedding=_get_embeddings(),
    )
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 1})


@tool
def retrieve_information(query: str) -> str:
    """Search and return information related to the gym from the gym information document."""
    retriever = _get_retriever()
    retrieved_docs = retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in retrieved_docs])