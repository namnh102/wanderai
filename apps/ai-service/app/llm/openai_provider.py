import openai
from typing import List, Dict, Any
from app.llm.base import BaseLLMProvider
from app.config import settings

class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"
        
    async def chat(self, messages: List[Dict[str, Any]], system_prompt: str) -> str:
        api_messages = [{"role": "system", "content": system_prompt}] + messages
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=api_messages
        )
        return response.choices[0].message.content

    async def chat_with_tools(self, messages: List[Dict[str, Any]], tools: List[Any], system_prompt: str) -> dict:
        api_messages = [{"role": "system", "content": system_prompt}] + messages
        
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            })
            
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            tools=openai_tools if tools else None
        )
        
        message = response.choices[0].message
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                import json
                tool_calls.append({
                    "name": tc.function.name,
                    "args": json.loads(tc.function.arguments)
                })
                
        return {
            "response": message.content or "",
            "tool_calls": tool_calls
        }
