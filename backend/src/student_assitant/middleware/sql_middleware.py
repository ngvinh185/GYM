from typing import Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call

from student_assitant.prompt.sql_prompt import ADMIN_ROLE_PROMPT, USER_ROLE_PROMPT


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