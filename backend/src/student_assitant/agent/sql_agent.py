
from student_assitant.middleware.sql_middleware import injectSystemPrompt, SqlTrace
from student_assitant.prompt.sql_prompt import SQL_AGENT_SYSTEM_PROMPT
from student_assitant.tools.sql_tools import get_sql_tool

from student_assitant.middleware.sql_middleware import SQLStateMiddleware


def create_sql_subagent(db) -> dict:
    return {
        "name": "sql-agent",
        "description": (
            "Truy vấn cơ sở dữ liệu phòng gym bằng SQL: sinh query, chạy, "
            "và tóm tắt kết quả. Dùng khi cần dữ liệu từ database."
        ),
        "system_prompt": SQL_AGENT_SYSTEM_PROMPT,
        "tools": get_sql_tool(db),
        "skills": ["/skills/"],
        "middleware": [
            SQLStateMiddleware(),
            injectSystemPrompt,
            SqlTrace(),
            # chốt chặn chống loop: vượt giới hạn thì tool bị chặn, model nhận thông báo lỗi
            # ToolCallLimitMiddleware(tool_name="ls", run_limit=2, exit_behavior="continue"),
            # ToolCallLimitMiddleware(run_limit=15, exit_behavior="continue"),
            # ModelCallLimitMiddleware(run_limit=20, exit_behavior="end"),
        ],
    }