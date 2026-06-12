from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch
import pytest

client = TestClient(app)

def test_chat_endpoint():
    with patch("app.api.routes.chat.chat_with_tempo") as mock_chat, \
         patch("app.api.routes.chat.extract_memories") as mock_extract:
        mock_chat.return_value = {
            "reply": "Hello! I am Tempo, your study coordinator.",
            "tool_calls": []
        }
        
        response = client.post(
            "/api/chat",
            json={"message": "Hello, I am a new student.", "user_id": "test_user"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "message_id" in data
        assert data["reply"] == "Hello! I am Tempo, your study coordinator."

