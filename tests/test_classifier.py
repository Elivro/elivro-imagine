"""Tests for task classification and intent detection."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from elivroimagine.classifier import (
    ClassificationError,
    TaskClassification,
    classify_transcription,
)


def _mock_api_response(data: dict) -> MagicMock:
    """Create a mock requests.post response returning the given JSON."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(data)}}]
    }
    return resp


class TestCreateIntent:
    """Test classification with create intent."""

    @patch("elivroimagine.classifier.requests.post")
    def test_create_intent_all_fields(self, mock_post: MagicMock) -> None:
        """Create intent populates all fields."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "create",
                "title": "Fix login button",
                "description": "The login button is broken on mobile",
                "category": "Frontend",
                "priority": "high",
                "effort": "small",
            }
        )

        result = classify_transcription(
            "fix the login button", "fake-key", categories=["Frontend", "Backend"]
        )

        assert result.intent == "create"
        assert result.title == "Fix login button"
        assert result.description == "The login button is broken on mobile"
        assert result.category == "Frontend"
        assert result.priority == "high"
        assert result.effort == "small"
        assert result.task_id is None

    @patch("elivroimagine.classifier.requests.post")
    def test_missing_intent_defaults_to_create(self, mock_post: MagicMock) -> None:
        """Missing intent field defaults to create."""
        mock_post.return_value = _mock_api_response(
            {
                "title": "Add dark mode",
                "description": "Support dark theme",
                "category": "Frontend",
                "priority": "medium",
                "effort": "medium",
            }
        )

        result = classify_transcription("add dark mode", "fake-key")

        assert result.intent == "create"
        assert result.title == "Add dark mode"
        assert result.task_id is None

    @patch("elivroimagine.classifier.requests.post")
    def test_unknown_intent_defaults_to_create(self, mock_post: MagicMock) -> None:
        """Unknown intent value defaults to create."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "delete",
                "title": "Some task",
                "description": "Desc",
                "category": "General",
                "priority": "low",
                "effort": "tiny",
            }
        )

        result = classify_transcription("delete something", "fake-key")

        assert result.intent == "create"

    @patch("elivroimagine.classifier.requests.post")
    def test_create_validates_priority_and_effort(self, mock_post: MagicMock) -> None:
        """Invalid priority/effort fall back to medium for create."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "create",
                "title": "Task",
                "description": "Desc",
                "category": "General",
                "priority": "urgent",
                "effort": "huge",
            }
        )

        result = classify_transcription("do something", "fake-key")

        assert result.priority == "medium"
        assert result.effort == "medium"

    @patch("elivroimagine.classifier.requests.post")
    def test_create_fuzzy_matches_category(self, mock_post: MagicMock) -> None:
        """Category fuzzy-matches against provided list."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "create",
                "title": "Task",
                "description": "Desc",
                "category": "front",
                "priority": "low",
                "effort": "small",
            }
        )

        result = classify_transcription(
            "task", "fake-key", categories=["Frontend", "Backend"]
        )

        assert result.category == "Frontend"


class TestUpdateIntent:
    """Test classification with update intent."""

    @patch("elivroimagine.classifier.requests.post")
    def test_update_with_task_id_and_fields(self, mock_post: MagicMock) -> None:
        """Update intent extracts task_id and changed fields only."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "update",
                "task_id": 42,
                "priority": "high",
            }
        )

        result = classify_transcription("update task 42 set priority high", "fake-key")

        assert result.intent == "update"
        assert result.task_id == 42
        assert result.priority == "high"
        # Unchanged fields should be None
        assert result.title is None
        assert result.description is None
        assert result.category is None
        assert result.effort is None

    @patch("elivroimagine.classifier.requests.post")
    def test_update_multiple_fields(self, mock_post: MagicMock) -> None:
        """Update intent with multiple changed fields."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "update",
                "task_id": 7,
                "title": "New title",
                "category": "Backend",
            }
        )

        result = classify_transcription(
            "rename task 7", "fake-key", categories=["Frontend", "Backend"]
        )

        assert result.intent == "update"
        assert result.task_id == 7
        assert result.title == "New title"
        assert result.category == "Backend"
        assert result.priority is None
        assert result.effort is None

    @patch("elivroimagine.classifier.requests.post")
    def test_update_missing_task_id_raises(self, mock_post: MagicMock) -> None:
        """Update intent without task_id raises ClassificationError."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "update",
                "priority": "high",
            }
        )

        with pytest.raises(ClassificationError, match="task_id"):
            classify_transcription("change priority to high", "fake-key")

    @patch("elivroimagine.classifier.requests.post")
    def test_update_invalid_task_id_raises(self, mock_post: MagicMock) -> None:
        """Update intent with non-integer task_id raises ClassificationError."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "update",
                "task_id": "abc",
                "priority": "high",
            }
        )

        with pytest.raises(ClassificationError, match="must be an integer"):
            classify_transcription("update task abc", "fake-key")

    @patch("elivroimagine.classifier.requests.post")
    def test_update_validates_priority(self, mock_post: MagicMock) -> None:
        """Invalid priority in update falls back to medium."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "update",
                "task_id": 10,
                "priority": "super-urgent",
            }
        )

        result = classify_transcription("update task 10", "fake-key")

        assert result.priority == "medium"

    @patch("elivroimagine.classifier.requests.post")
    def test_update_validates_effort(self, mock_post: MagicMock) -> None:
        """Invalid effort in update falls back to medium."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "update",
                "task_id": 10,
                "effort": "enormous",
            }
        )

        result = classify_transcription("update task 10", "fake-key")

        assert result.effort == "medium"

    @patch("elivroimagine.classifier.requests.post")
    def test_update_fuzzy_matches_category(self, mock_post: MagicMock) -> None:
        """Category fuzzy-matches for update intent too."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "update",
                "task_id": 5,
                "category": "back",
            }
        )

        result = classify_transcription(
            "update task 5", "fake-key", categories=["Frontend", "Backend"]
        )

        assert result.category == "Backend"

    @patch("elivroimagine.classifier.requests.post")
    def test_intent_case_insensitive(self, mock_post: MagicMock) -> None:
        """Intent matching is case-insensitive."""
        mock_post.return_value = _mock_api_response(
            {
                "intent": "UPDATE",
                "task_id": 1,
                "priority": "low",
            }
        )

        result = classify_transcription("update task 1", "fake-key")

        assert result.intent == "update"
        assert result.task_id == 1
