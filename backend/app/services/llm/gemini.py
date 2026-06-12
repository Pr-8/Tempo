from typing import List, Dict, Any, Optional
from datetime import datetime
from google import genai
from google.genai import types
from app.core.config import settings
from .prompts import EXPLANATION_PROMPT_SYSTEM, build_explanation_prompt
from .tools import TOOLS
from .tool_executor import execute_tool

def generate_schedule_explanation(tasks: list, sessions: list) -> str:
    if settings.GEMINI_API_KEY == "fallback":
        return "Your schedule has been updated. (Gemini API key not configured)"

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=10000,
            retry_options=types.HttpRetryOptions(attempts=1)
        )
    )
    
    now = datetime.now()
    now_str = now.strftime("%A, %B %d, %Y at %H:%M")
    tasks_str = "\n".join([f"- {t.title} ({t.course}): {t.remaining_hours}h left, due {t.deadline}" for t in tasks])
    sessions_str = "\n".join([f"- {s.start_time.strftime('%Y-%m-%d %H:%M')}: {s.duration_minutes}m of {s.task_id}" for s in sessions])
    
    prompt = build_explanation_prompt(tasks_str, sessions_str, current_datetime=now_str)
    
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=[
                EXPLANATION_PROMPT_SYSTEM,
                prompt
            ]
        )
        return response.text
    except Exception as e:
        return f"Your schedule has been updated. (Explanation generation failed: {str(e)})"

def chat_with_tempo(message: str, history: List[Dict[str, Any]] = None, system_instruction: str = None) -> Dict[str, Any]:
    """
    Chat with Tempo using the Gemini 2.0 Flash model and tool calling.
    """
    if settings.GEMINI_API_KEY == "fallback":
        return {"reply": "Gemini API key not configured.", "tool_calls": []}

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=15000,
            retry_options=types.HttpRetryOptions(attempts=2)
        )
    )
    
    # Convert tool definitions to Google GenAI types if necessary
    # The new SDK can take the JSON-like definitions directly in tools=[]
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[{"function_declarations": TOOLS}],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )

    # Convert history to Gemini format
    contents = []
    if history:
        for h in history:
            role = "model" if h["role"] == "assistant" else h["role"]
            contents.append(types.Content(role=role, parts=[types.Part(text=h["content"])]))
    
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

    tool_calls_log = []
    max_iterations = 5
    
    try:
        for _ in range(max_iterations):
            response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
                contents=contents,
                config=config
            )
            
            candidate = response.candidates[0]
            contents.append(candidate.content) # Add model response to conversation
            
            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if part.function_call
            ]
            
            if not function_calls:
                final_text = "".join(part.text for part in candidate.content.parts if part.text)
                return {"reply": final_text, "tool_calls": tool_calls_log}
            
            tool_responses = []
            for fc in function_calls:
                result = execute_tool(fc.name, fc.args)
                
                tool_calls_log.append({
                    "tool": fc.name,
                    "args": fc.args,
                    "result": result
                })
                
                tool_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": result}
                        )
                    )
                )
            
            # Add tool results to conversation
            contents.append(types.Content(role="tool", parts=tool_responses))
            
        return {"reply": "I'm having trouble completing that request. Could you rephrase?", "tool_calls": tool_calls_log}

    except Exception as e:
        return {"reply": f"An error occurred: {str(e)}", "tool_calls": tool_calls_log}
