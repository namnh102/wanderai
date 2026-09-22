import google.generativeai as genai
from typing import List, Dict, Any
from app.llm.base import BaseLLMProvider
from app.config import settings

class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-2.0-flash"
        
    async def chat(self, messages: List[Dict[str, Any]], system_prompt: str) -> str:
        prompt = f"System: {system_prompt}\n\n"
        for m in messages:
            prompt += f"{m['role']}: {m['content']}\n"
            
        model = genai.GenerativeModel(self.model_name)
        response = model.generate_content(prompt)
        return response.text

    async def chat_with_tools(self, messages: List[Dict[str, Any]], tools: List[Any], system_prompt: str) -> dict:
        prompt = f"System: {system_prompt}\n\n"
        for m in messages:
            prompt += f"{m['role']}: {m['content']}\n"
            
        # Simplified tool representation for implementation demo
        gemini_tools = [{"function_declarations": [{"name": t.name, "description": t.description, "parameters": t.parameters}]} for t in tools]
        
        model = genai.GenerativeModel(self.model_name, tools=gemini_tools if tools else None)
        response = model.generate_content(prompt)
        
        # Simplified parser
        tool_calls = []
        if response.parts:
            for part in response.parts:
                if hasattr(part, "function_call") and part.function_call:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": {k: v for k, v in part.function_call.args.items()}
                    })
        
        return {
            "response": response.text,
            "tool_calls": tool_calls
        }
