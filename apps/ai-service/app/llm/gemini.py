"""Gemini LLM Provider — Function Calling chuan"""
import asyncio
import json
from google import genai
from google.genai import types
from app.config import settings
from app.prompts.system_prompt import SYSTEM_PROMPT

_client = genai.Client(api_key=settings.GEMINI_API_KEY)
_MODEL = "gemini-3.5-flash"


def _tool_to_function_declaration(tool) -> types.FunctionDeclaration:
    """Chuyen BaseTool sang Gemini FunctionDeclaration"""
    props = {}
    for k, v in tool.parameters.get("properties", {}).items():
        schema_kwargs = {
            "type": _map_type(v.get("type", "string")),
        }
        if v.get("description"):
            schema_kwargs["description"] = v["description"]
        if v.get("enum"):
            schema_kwargs["enum"] = v["enum"]
        props[k] = types.Schema(**schema_kwargs)

    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties=props,
            required=tool.parameters.get("required", []),
        ),
    )


def _map_type(t: str) -> types.Type:
    return {
        "string": types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number": types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
        "array": types.Type.ARRAY,
        "object": types.Type.OBJECT,
    }.get(t, types.Type.STRING)


class GeminiProvider:
    """Goi Gemini API voi Function Calling"""

    def __init__(self):
        self._histories: dict[str, list] = {}

    async def chat(self, message: str, session_id: str = "default") -> str:
        result = await self.chat_with_tools(message, tools=[], session_id=session_id)
        return result["response"]

    async def chat_with_tools(
        self,
        message: str,
        tools: list,
        session_id: str = "default",
    ) -> dict:
        """
        Chat voi Gemini + Function Calling.
        Returns: {"response": str, "tool_calls": list[dict]}
        """
        try:
            # Build tool declarations
            gemini_tools = None
            tool_map = {}
            if tools:
                declarations = [_tool_to_function_declaration(t) for t in tools]
                gemini_tools = [types.Tool(function_declarations=declarations)]
                tool_map = {t.name: t for t in tools}

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=4096,
                tools=gemini_tools or [],
            )

            # Lay history cu
            history = self._get_history(session_id)

            # Build contents: history + user message moi
            contents = list(history) + [
                types.Content(role="user", parts=[types.Part(text=message)])
            ]

            tool_calls_log = []

            # Vong lap Agent: toi da 5 buoc
            for iteration in range(5):
                # Goi Gemini
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda c=contents, cfg=config: _client.models.generate_content(
                        model=_MODEL,
                        contents=c,
                        config=cfg,
                    ),
                )

                if not response.candidates:
                    break

                candidate = response.candidates[0]
                if not candidate.content or not candidate.content.parts:
                    break

                # Kiem tra co function call khong
                fn_calls_in_response = []
                for part in candidate.content.parts:
                    if part.function_call:
                        fn_calls_in_response.append(part.function_call)

                if not fn_calls_in_response:
                    # Khong co function call -> lay text cuoi cung
                    break

                # Co function call -> thuc thi tung tool
                fn_response_parts = []
                for fn in fn_calls_in_response:
                    tool_name = fn.name
                    tool_args = dict(fn.args) if fn.args else {}

                    tool_log = {"tool": tool_name, "args": tool_args, "result": None}

                    if tool_name in tool_map:
                        try:
                            result = await tool_map[tool_name].execute(tool_args)
                            tool_log["result"] = result
                        except Exception as e:
                            result = {"error": str(e)}
                            tool_log["result"] = result
                    else:
                        result = {"error": f"Tool {tool_name} not found"}
                        tool_log["result"] = result

                    tool_calls_log.append(tool_log)

                    fn_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={"result": json.dumps(result, ensure_ascii=False, default=str)},
                            )
                        )
                    )

                # Them model response + function results vao contents
                # Model response giu nguyen (role=model, parts chua function_call)
                contents.append(candidate.content)
                # Function results gui voi role=user (Gemini API chi chap nhan user/model)
                contents.append(types.Content(role="user", parts=fn_response_parts))

            # Lay text cuoi cung tu response
            final_text = ""
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        final_text += part.text

            if not final_text:
                final_text = "Xin loi, minh chua the tra loi. Ban thu lai nhe!"

            # Luu history (chi luu user message + final model text)
            history.append(
                types.Content(role="user", parts=[types.Part(text=message)])
            )
            history.append(
                types.Content(role="model", parts=[types.Part(text=final_text)])
            )
            # Giu toi da 20 turns (40 items)
            if len(history) > 40:
                self._histories[session_id] = history[-40:]

            return {
                "response": final_text,
                "tool_calls": tool_calls_log,
            }

        except Exception as e:
            err_type = type(e).__name__
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                error_msg = "Hien tai AI dang ban, ban doi 1 phut roi thu lai nhe!"
            elif "503" in str(e) or "UNAVAILABLE" in str(e):
                error_msg = "Server AI dang qua tai, thu lai sau vai giay nhe!"
            else:
                error_msg = f"Loi ky thuat ({err_type}). Ban thu lai nhe!"
            return {"response": error_msg, "tool_calls": []}

    def _get_history(self, session_id: str) -> list:
        if session_id not in self._histories:
            self._histories[session_id] = []
        return self._histories[session_id]

    def clear_session(self, session_id: str):
        self._histories.pop(session_id, None)


# Singleton
gemini_provider = GeminiProvider()
