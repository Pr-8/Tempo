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
    },
    {
        "name": "get_tasks",
        "description": "Get all current tasks for the user. Returns task details including title, course, deadline, priority, status, remaining hours, and whether the task is fixed. Use this to answer questions about what tasks exist, check deadlines, or find a task before updating/completing it.",
        "parameters": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "description": "Optional. Filter tasks by status. If omitted, returns all non-completed tasks.",
                    "enum": ["all", "pending", "in_progress", "completed"]
                }
            },
            "required": []
        }
    },
    {
        "name": "update_task",
        "description": "Update properties of an existing task. Use get_tasks first to find the task title if unsure. You can update the deadline, priority, estimated hours, title, or course. Only provide the fields you want to change.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_title": {
                    "type": "string",
                    "description": "The current title of the task to update. Must match an existing task (case-insensitive partial match is supported)."
                },
                "new_title": {
                    "type": "string",
                    "description": "New title for the task."
                },
                "new_deadline": {
                    "type": "string",
                    "description": "New deadline in ISO 8601 date format (YYYY-MM-DD). The time will be set to 23:59."
                },
                "new_priority": {
                    "type": "string",
                    "description": "New priority level.",
                    "enum": ["low", "medium", "high"]
                },
                "new_estimated_hours": {
                    "type": "number",
                    "description": "New estimated total hours for the task. Must be >= remaining_hours unless you also intend to reset progress."
                },
                "new_course": {
                    "type": "string",
                    "description": "New course/category for the task."
                }
            },
            "required": ["task_title"]
        }
    },
    {
        "name": "complete_task",
        "description": "Mark a task as completed. This removes all future scheduled sessions for the task and triggers a reschedule. Use get_tasks first if unsure of the exact task title.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_title": {
                    "type": "string",
                    "description": "The title of the task to mark as completed. Case-insensitive partial match is supported."
                }
            },
            "required": ["task_title"]
        }
    },
    {
        "name": "delete_task",
        "description": "Permanently delete a task and all its scheduled sessions. This cannot be undone. Use get_tasks first if unsure of the exact task title.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_title": {
                    "type": "string",
                    "description": "The title of the task to delete. Case-insensitive partial match is supported."
                }
            },
            "required": ["task_title"]
        }
    },
    {
        "name": "log_progress",
        "description": "Log study progress on a task by specifying how many hours were completed. This reduces the remaining hours for the task. If remaining hours reach 0, the task is automatically marked as completed.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_title": {
                    "type": "string",
                    "description": "The title of the task to log progress for. Case-insensitive partial match is supported."
                },
                "hours_completed": {
                    "type": "number",
                    "description": "Number of hours of work completed. Can be decimal (e.g., 1.5 for 90 minutes)."
                }
            },
            "required": ["task_title", "hours_completed"]
        }
    },
    {
        "name": "get_memories",
        "description": "Retrieve stored memories/facts about the user. Use this when the user asks what you know or remember about them, or when you need to check stored context before making a decision.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search query to filter memories by relevance. If omitted, returns all memories."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to return. Default is 20."
                }
            },
            "required": []
        }
    },
    {
        "name": "reschedule",
        "description": "Trigger a full schedule regeneration. Use this when the user explicitly asks to reschedule, regenerate, or redo their schedule. This runs the constraint solver in the background and pushes updates via WebSocket.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Optional reason for rescheduling, used for logging."
                }
            },
            "required": []
        }
    }
]
