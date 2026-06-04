TOOLS = [
    {
        "name": "add_task",
        "description": "Add a new study task or event to the user's schedule.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "course": {"type": "string"},
                "is_fixed": {"type": "boolean", "description": "True for fixed-time events, False for flexible tasks."},
                "estimated_hours": {"type": "number", "description": "Hours needed for flexible tasks."},
                "deadline": {"type": "string", "description": "ISO date YYYY-MM-DD for tasks."},
                "fixed_start": {"type": "string", "description": "ISO datetime for events."},
                "fixed_end": {"type": "string", "description": "ISO datetime for events."},
                "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Mapped to 1 (low), 3 (medium), 5 (high)."}
            },
            "required": ["title", "is_fixed", "priority"]
        }
    },
    {
        "name": "block_time",
        "description": "Block out a specific date as unavailable.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "reason": {"type": "string"}
            },
            "required": ["date"]
        }
    },
    {
        "name": "get_schedule",
        "description": "Retrieve schedule for a date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD"}
            },
            "required": ["start_date", "end_date"]
        }
    },
    {
        "name": "update_preference",
        "description": "Update user working hours or session limits.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "enum": ["day_start", "day_end", "max_sessions_per_day", "min_break_minutes", "preferred_session_mins", "max_session_mins"]
                },
                "value": {"type": "string"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "ask_clarification",
        "description": "Ask the user a clarifying question.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"}
            },
            "required": ["question"]
        }
    }
]
