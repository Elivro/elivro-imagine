"""Tests for DevTracker API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from elivroimagine.devtracker import DevTrackerClient, DevTrackerError


def _make_client() -> DevTrackerClient:
    """Create a DevTrackerClient with mock config."""
    config = MagicMock()
    config.api_url = "https://api.example.com"
    config.api_key = "test-key"
    config.email = "dev@example.com"
    config.project = "test-project"
    return DevTrackerClient(config)


class TestUpdateTask:
    """Test update_task method."""

    def test_sends_patch_with_provided_fields(self) -> None:
        """update_task sends PATCH with only non-None fields."""
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "task": {"id": 42, "title": "Updated", "priority": "high"}
        }
        mock_resp.raise_for_status = MagicMock()
        client._session.patch = MagicMock(return_value=mock_resp)

        result = client.update_task(task_id=42, priority="high")

        client._session.patch.assert_called_once()
        call_args = client._session.patch.call_args
        assert "/tasks/42" in call_args.args[0]
        assert call_args.kwargs["json"] == {"priority": "high"}
        assert result == {"id": 42, "title": "Updated", "priority": "high"}

    def test_sends_multiple_fields(self) -> None:
        """update_task sends all non-None fields."""
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"task": {"id": 10}}
        mock_resp.raise_for_status = MagicMock()
        client._session.patch = MagicMock(return_value=mock_resp)

        client.update_task(task_id=10, title="New title", category=3, effort="large")

        payload = client._session.patch.call_args.kwargs["json"]
        assert payload == {"title": "New title", "category": 3, "effort": "large"}

    def test_empty_payload_raises_error(self) -> None:
        """update_task with no fields raises DevTrackerError."""
        client = _make_client()

        with pytest.raises(DevTrackerError, match="No fields to update"):
            client.update_task(task_id=42)

    def test_api_error_wraps_in_devtracker_error(self) -> None:
        """API errors are wrapped in DevTrackerError with task ID."""
        client = _make_client()
        client._session.patch = MagicMock(
            side_effect=requests.RequestException("404 Not Found")
        )

        with pytest.raises(DevTrackerError, match="Failed to update task #42"):
            client.update_task(task_id=42, priority="high")

    def test_sends_description_field(self) -> None:
        """update_task sends description when provided."""
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"task": {"id": 5}}
        mock_resp.raise_for_status = MagicMock()
        client._session.patch = MagicMock(return_value=mock_resp)

        client.update_task(task_id=5, description="New desc")

        payload = client._session.patch.call_args.kwargs["json"]
        assert payload == {"description": "New desc"}


class TestCreateTaskRegression:
    """Verify create_task still works after adding update_task."""

    def test_create_task_sends_post(self) -> None:
        """create_task sends POST to /tasks."""
        client = _make_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "task": {"id": 99, "title": "New task"}
        }
        mock_resp.raise_for_status = MagicMock()
        client._session.post = MagicMock(return_value=mock_resp)

        result = client.create_task(
            title="New task",
            description="Description",
            priority="medium",
            effort="small",
        )

        client._session.post.assert_called_once()
        call_args = client._session.post.call_args
        assert "/tasks" in call_args.args[0]
        assert result == {"id": 99, "title": "New task"}
