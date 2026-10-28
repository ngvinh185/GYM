

from langchain.tools import tool
from student_assitant.pdf.pdf_handle import get_docs

from student_assitant.pdf.pdf_handle import _get_retriever



@tool
def retrieve_information(query: str) -> str:
    """Search and return information related to the gym from the gym information document."""
    retriever = _get_retriever()
    retrieved_docs = retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in retrieved_docs])