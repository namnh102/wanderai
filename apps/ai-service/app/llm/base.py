from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: List[Dict[str, Any]], system_prompt: str) -> str:
        pass

    @abstractmethod
    async def chat_with_tools(self, messages: List[Dict[str, Any]], tools: List[Any], system_prompt: str) -> dict:
        pass
