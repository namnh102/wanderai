"""Gemini LLM Provider — Gọi Google Gemini API thật"""
import google.generativeai as genai
from app.config import settings
from app.prompts.system_prompt import SYSTEM_PROMPT

# Khởi tạo Gemini client
genai.configure(api_key=settings.GEMINI_API_KEY)


class GeminiProvider:
    """Gọi Gemini API để chat du lịch"""

    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-3.6-flash",
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
                top_p=0.9,
            ),
        )
        # Cache chat sessions theo session_id
        self._sessions: dict[str, any] = {}

    def get_or_create_session(self, session_id: str):
        """Lấy hoặc tạo chat session mới"""
        if session_id not in self._sessions:
            self._sessions[session_id] = self.model.start_chat(history=[])
        return self._sessions[session_id]

    async def chat(self, message: str, session_id: str = "default") -> str:
        """Gửi message đến Gemini, trả về response text"""
        try:
            chat_session = self.get_or_create_session(session_id)
            response = chat_session.send_message(message)
            return response.text
        except Exception as e:
            return f"Xin lỗi, mình gặp lỗi: {str(e)}. Bạn thử hỏi lại nhé! 😊"

    def clear_session(self, session_id: str):
        """Xóa chat session"""
        self._sessions.pop(session_id, None)


# Singleton instance
gemini_provider = GeminiProvider()
