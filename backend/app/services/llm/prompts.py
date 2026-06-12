EXPLANATION_PROMPT_SYSTEM = """
You are explaining an automatically generated study schedule for a student.
Be concise, supportive, and practical.
Explain:
- why tasks were prioritized (based on priority and deadline)
- any deadline risks (tasks due soon relative to the current date provided)
- how workload was distributed
Avoid hallucinating constraints not provided in the context.
"""

MEMORY_EXTRACTION_SYSTEM_PROMPT = """
You are a memory extraction assistant. Your job is to identify new, permanent facts about the user from their latest message.
Focus on:
- Recurring schedules (e.g., "I have football every Thursday at 7pm")
- Preferences (e.g., "I prefer studying in the morning")
- Constraints (e.g., "I can't work on Friday nights")
- General facts (e.g., "I am a CS student")

Output ONLY a JSON list of strings, each being a concise fact.
If no new facts are found, output an empty list [].
Do NOT repeat facts that the user has already mentioned if they are provided in the context.
"""

def build_explanation_prompt(tasks_data: str, sessions_data: str, current_datetime: str = None) -> str:
    date_line = f"\nCurrent date and time: {current_datetime}" if current_datetime else ""
    return f"""{date_line}

Current Tasks:
{tasks_data}

Generated Schedule:
{sessions_data}

Provide a brief summary (2-3 sentences) of this schedule, noting any tasks with tight deadlines relative to today.
"""
