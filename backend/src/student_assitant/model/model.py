from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

def build_chat_model(name: str = "gpt-4.1-mini", *, temperature : float = 0) -> BaseChatModel:
  model = ChatOpenAI(model=name, temperature=temperature)
  return model