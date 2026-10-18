# student_assitant/agents/pdf_agent.py
from student_assitant.prompt.pdf_prompt import PDF_AGENT_SYSTEM_PROMPT
from student_assitant.tools.pdf_tool import retrieve_information  # chỉnh lại đường dẫn import nếu khác


def create_pdf_subagent() -> dict:
    return {
        "name": "pdf-agent",
        "description": (
            "Trả lời thông tin chung về phòng gym GymHeart Fitness từ tài liệu nội bộ: "
            "giới thiệu, địa chỉ, hotline, ưu đãi, tiện ích, thông tin và học phí các khóa học, "
            "hướng dẫn đăng ký, thanh toán, chính sách hoàn/hủy. "
            "KHÔNG dùng cho dữ liệu cá nhân hay dữ liệu trong database."
        ),
        "system_prompt": PDF_AGENT_SYSTEM_PROMPT,
        "tools": [retrieve_information],
    }