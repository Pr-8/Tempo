import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def generate_schedule_explanation(solver_output: dict, tasks: list) -> str:
    """
    Uses Gemini to explain the scheduling decisions in plain English.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Schedule updated successfully."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-flash-latest")

        task_lookup = {str(t["id"]): t for t in tasks}
        
        # Summarise scheduled sessions
        scheduled_summary = []
        for s in solver_output.get("scheduled_sessions", []):
            task = task_lookup.get(str(s["task_id"]), {})
            title = task.get("title", "Unknown Task")
            scheduled_summary.append(f"- {title}: {s['start']} to {s['end']}")
            
        # Summarise unschedulable tasks
        unschedulable = []
        for tid in solver_output.get("unschedulable_tasks", []):
            task = task_lookup.get(str(tid), {})
            unschedulable.append(task.get("title", str(tid)))
            
        unschedulable_str = ", ".join(unschedulable) if unschedulable else "None — all tasks fit."

        system_instruction = (
            "You are a practical study coach. A scheduling algorithm has produced "
            "the study plan below for a student. Write 3-4 sentences explaining: "
            "1. What was prioritised first and why, 2. Any heavy days or potential pressure points, "
            "3. Any tasks that could NOT be scheduled. "
            "Be direct. Use plain English. No bullet points. Address the student as 'you'. "
            "Do NOT repeat the schedule — only flag things worth knowing."
        )

        user_message = f"""
SCHEDULED SESSIONS:
{chr(10).join(scheduled_summary)}

TASKS THAT COULD NOT BE SCHEDULED:
{unschedulable_str}

TASK DETAILS:
{json.dumps([{
    'title': t.get('title'),
    'deadline': t.get('deadline'),
    'priority': t.get('priority'),
    'remaining_hours': t.get('remaining_hours')
} for t in tasks], indent=2)}
"""

        response = model.generate_content(
            f"{system_instruction}\n\n{user_message}"
        )
        
        return response.text.strip() if response.text else "Schedule updated successfully."

    except Exception as e:
        print(f"Error generating schedule explanation: {e}")
        return "Schedule updated successfully."
