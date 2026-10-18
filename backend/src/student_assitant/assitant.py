from langgraph.checkpoint.memory import InMemorySaver

from student_assitant.agent.deep_agent import create_deepagent
from student_assitant.agent.pdf_agent import create_pdf_subagent
from student_assitant.agent.sql_agent import MainStateMiddleware, create_sql_subagent
from student_assitant.config import Settings, backend
from student_assitant.database.database import Database
from student_assitant.middleware.deepagent_middleware import injectSystemPromptDeepagent
from student_assitant.model.model import build_chat_model
from student_assitant.prompt.deepagent_prompt import MAIN_SYSTEM_PROMPT


class Graph:
  def __init__(self, user_role: str, user_id: str):
      self.user_role = user_role
      self.user_id = user_id
      self.is_admin = user_role.upper() == "ADMIN"
      self.agent = self.create_agent()

  def create_agent(self):
    settings = Settings.from_env()
    db = Database(settings.db, is_admin=self.is_admin)
    return create_deepagent(
        model=build_chat_model(),
        system_prompt=MAIN_SYSTEM_PROMPT,
        subagents=[create_sql_subagent(db), create_pdf_subagent()],
        backend=backend,
        checkpointer=InMemorySaver(),
        middleware=[MainStateMiddleware(), injectSystemPromptDeepagent],
    )

  def invoke(self, message: str, thread_id: str):
    return self.agent.invoke(
        {
            "messages": [{"role": "user", "content": message}],
            "user_role": self.user_role,
            "user_id": self.user_id,
        },
        config={"configurable": {"thread_id": thread_id}},
    )