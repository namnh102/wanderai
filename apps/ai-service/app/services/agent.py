from typing import Dict, Any, List
from app.llm.gemini import GeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.config import settings
from app.tools.search_places import SearchPlacesTool
from app.tools.get_weather import GetWeatherTool
from app.tools.calculate_budget import CalculateBudgetTool
from app.tools.search_hotels import SearchHotelsTool
from app.tools.calculate_route import CalculateRouteTool
from app.tools.search_reviews import SearchReviewsTool
from app.services.cache import CacheService
from app.services.rag import RAGService
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.planner import PlanRequest, PlanResponse

class TravelAgent:
    def __init__(self):
        if settings.LLM_PROVIDER == "openai":
            self.llm = OpenAIProvider()
        else:
            self.llm = GeminiProvider()
            
        self.tools = [
            SearchPlacesTool(), GetWeatherTool(), CalculateBudgetTool(),
            SearchHotelsTool(), CalculateRouteTool(), SearchReviewsTool()
        ]
        self.cache = CacheService()
        self.rag = RAGService()

    async def input_guard(self, text: str) -> bool:
        # Basic prompt injection sanitization
        suspicious = ["ignore all previous instructions", "system prompt", "bypass"]
        if any(s in text.lower() for s in suspicious):
            raise ValueError("Input failed safety check")
        return True

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        await self.input_guard(request.message)
        
        # Check cache
        cache_key = f"chat_{request.session_id}_{request.message}"
        cached = await self.cache.get(cache_key)
        if cached:
            return ChatResponse(response=cached, tool_calls=[], sources=[])
            
        # Get RAG context
        context = await self.rag.search_similar(request.message)
        
        # Call LLM with tools
        messages = [{"role": "user", "content": request.message}]
        if context:
            messages.insert(0, {"role": "system", "content": f"Context information:\n{context}"})
            
        llm_res = await self.llm.chat_with_tools(messages, self.tools, SYSTEM_PROMPT)
        
        response_text = llm_res.get("response", "")
        
        # Validate output (dummy validation)
        if not response_text:
            response_text = "I could not generate a response."
            
        # Set cache
        await self.cache.set(cache_key, response_text, ttl=3600)
        
        return ChatResponse(
            response=response_text,
            tool_calls=llm_res.get("tool_calls", []),
            sources=[]
        )

    async def handle_plan(self, request: PlanRequest) -> PlanResponse:
        await self.input_guard(f"Plan trip to {request.destination}")
        
        cache_key = f"plan_{request.destination}_{request.days}_{request.budget}"
        cached = await self.cache.get(cache_key)
        if cached:
            pass # Use cached
            
        messages = [{"role": "user", "content": f"Create a {request.days}-day itinerary for {request.destination}. Budget: {request.budget}. Style: {request.style}. Interests: {', '.join(request.interests)}."}]
        
        llm_res = await self.llm.chat(messages, SYSTEM_PROMPT)
        
        from app.schemas.planner import ItineraryDay, ItineraryItem
        
        day1 = ItineraryDay(
            day=1,
            date="Day 1",
            items=[ItineraryItem(time="09:00", activity="Arrive", location=request.destination, description="Welcome!", cost_estimate=0)]
        )
        
        return PlanResponse(
            destination=request.destination,
            total_days=request.days,
            itinerary=[day1],
            total_budget_estimate=1000
        )
