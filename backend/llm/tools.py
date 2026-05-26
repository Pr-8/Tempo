TOOLS = [
    {
        "name": "add_task",
        "description": (
            "Add a new study task to the user's schedule. "
            "Use this when the user mentions a new assignment, exam, or deadline."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title":           {"type": "string"},
                "course":          {"type": "string", "nullable": True},
                "is_fixed":        {"type": "boolean", "description": "True if this is an Event (fixed time), False if it is a Task (flexible time)."},
                "estimated_hours": {"type": "number", "description": "Needed for Tasks. For Events, it is calculated from start/end."},
                "deadline":        {"type": "string", "description": "ISO date YYYY-MM-DD. Needed for Tasks."},
                "fixed_start":     {"type": "string", "description": "ISO datetime. Needed for Events or Tasks with a draft time."},
                "fixed_end":       {"type": "string", "description": "ISO datetime. Needed for Events or Tasks with a draft time."},
                "priority":        {"type": "string", "enum": ["low","medium","high"]}
            },
            "required": ["title", "is_fixed", "priority"]
        }
    },
    {
        "name": "move_session",
        "description": "Move a scheduled session to a different time.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id":     {"type": "string"},
                "new_start_time": {"type": "string", "description": "ISO datetime"}
            },
            "required": ["session_id", "new_start_time"]
        }
    },
    {
        "name": "block_time",
        "description": (
            "Block out a date or time range so nothing gets scheduled there. "
            "Use when the user says they are unavailable at a certain time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date":   {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "reason": {"type": "string", "nullable": True}
            },
            "required": ["date"]
        }
    },
    {
        "name": "get_schedule",
        "description": "Retrieve the current schedule for a date range so you can answer questions about it.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "end_date":   {"type": "string", "description": "ISO date YYYY-MM-DD"}
            },
            "required": ["start_date", "end_date"]
        }
    },
    {
        "name": "update_preference",
        "description": "Update a user preference such as working hours or max sessions per day.",
        "parameters": {
            "type": "object",
            "properties": {
                "key":   {"type": "string",
                          "description": "One of: day_start, day_end, max_sessions_per_day, min_break_minutes, preferred_session_mins, max_session_mins"},
                "value": {"type": "string"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "ask_clarification",
        "description": (
            "Ask the user a specific clarifying question when required fields "
            "are missing or ambiguous. Only ask ONE question at a time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"}
            },
            "required": ["question"]
        }
    }
]
