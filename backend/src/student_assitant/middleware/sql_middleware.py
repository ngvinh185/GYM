from typing import Callable, NotRequired

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState)
from student_assitant.prompt.sql_prompt import ADMIN_ROLE_PROMPT, USER_ROLE_PROMPT
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
@wrap_model_call
def injectSystemPrompt(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    state = request.state
    if state.get("user_role") == "ADMIN":
        role_prompt = ADMIN_ROLE_PROMPT
    else:
        user_id = state.get("user_id") or "CHƯA XÁC ĐỊNH"
        role_prompt = USER_ROLE_PROMPT.format(user_id=user_id)

    # nối vào CUỐI để khớp với prompt ("PHÂN QUYỀN ở cuối system prompt")
    system_prompt = (request.system_prompt or "") + "\n\n" + role_prompt
    return handler(request.override(system_prompt=system_prompt))

class SqlTrace(AgentMiddleware):
    def after_agent(self, state):
        traces = []
        messages = state.get("messages", [])
        for m in messages:
            if isinstance(m, AIMessage):
                for tc in m.tool_calls:
                    traces.append(tc['name'])
        return {"sql_traces": traces}

class SQLState(AgentState):
    user_role: NotRequired[str]
    user_id: NotRequired[str]
    sql_traces: NotRequired[list]


class SQLStateMiddleware(AgentMiddleware):
    state_schema = SQLState
