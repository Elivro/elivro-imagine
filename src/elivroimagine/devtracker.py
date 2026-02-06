"""DevTracker REST API client for creating development tasks."""

from __future__ import annotations

import logging
import re

import requests

from .config import DevTrackerConfig

logger = logging.getLogger(__name__)


class DevTrackerError(Exception):
    """Raised when a DevTracker API operation fails."""

    pass


def normalize_title(title: str) -> str:
    """Normalize a title for comparison.

    Lowercases, strips whitespace, removes punctuation, collapses spaces.
    """
    normalized = title.lower().strip()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def find_duplicate_task(
    title: str, existing_tasks: list[dict[str, object]]
) -> dict[str, object] | None:
    """Find a task with a similar title in the existing list.

    Checks for exact match after normalization, then substring match
    with 80%+ length similarity.

    Returns:
        Matching task dict if found, None otherwise.
    """
    normalized_new = normalize_title(title)

    for task in existing_tasks:
        existing_title = str(task.get("title", ""))
        normalized_existing = normalize_title(existing_title)

        if normalized_new == normalized_existing:
            return task

        if normalized_new in normalized_existing or normalized_existing in normalized_new:
            len_ratio = min(len(normalized_new), len(normalized_existing)) / max(
                len(normalized_new), len(normalized_existing), 1
            )
            if len_ratio > 0.8:
                return task

    return None


class DevTrackerClient:
    """Client for the DevTracker REST API."""

    def __init__(self, config: DevTrackerConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "X-API-Key": config.api_key,
                "X-Developer-Email": config.email,
            }
        )
        self._categories: list[dict[str, object]] | None = None

    @property
    def _base_url(self) -> str:
        return self._config.api_url.rstrip("/")

    def get_categories(self) -> list[dict[str, object]]:
        """Get all categories (cached after first call)."""
        if self._categories is not None:
            return self._categories

        try:
            resp = self._session.get(f"{self._base_url}/categories", timeout=15)
            resp.raise_for_status()
            data = resp.json()
            self._categories = data.get("categories", [])
            return self._categories
        except requests.RequestException as e:
            raise DevTrackerError(f"Failed to fetch categories: {e}") from e

    def get_category_names(self) -> list[str]:
        """Get all category names for the project."""
        categories = self.get_categories()
        return [str(cat.get("name", "")) for cat in categories if cat.get("name")]

    def get_category_id(self, name: str) -> int | None:
        """Resolve a category name to its ID (case-insensitive).

        Returns:
            Category ID or None if not found.
        """
        categories = self.get_categories()
        name_lower = name.lower()
        for cat in categories:
            if str(cat.get("name", "")).lower() == name_lower:
                return int(cat["id"])  # type: ignore[arg-type]
        return None

    def get_active_and_backlog_tasks(self) -> list[dict[str, object]]:
        """Get all non-deployed tasks for duplicate detection."""
        try:
            resp = self._session.get(f"{self._base_url}/tasks", timeout=15)
            resp.raise_for_status()
            all_tasks: list[dict[str, object]] = resp.json().get("tasks", [])
            return [t for t in all_tasks if t.get("status") != "deployed"]
        except requests.RequestException as e:
            raise DevTrackerError(f"Failed to fetch tasks: {e}") from e

    def create_task(
        self,
        title: str,
        description: str,
        category: int | None = None,
        priority: str = "medium",
        effort: str = "medium",
        project_override: str | None = None,
    ) -> dict[str, object]:
        """Create a new DevTracker task.

        Args:
            title: Task title.
            description: Task description.
            category: Optional category ID.
            priority: Task priority level.
            effort: Task effort level.
            project_override: If set, use this project instead of the config default.

        Returns:
            Created task dict from the API.
        """
        payload: dict[str, object] = {
            "title": title,
            "description": description,
            "priority": priority,
            "effort": effort,
            "status": "backlog",
            "project": project_override or self._config.project,
        }
        if category is not None:
            payload["category"] = category

        try:
            resp = self._session.post(
                f"{self._base_url}/tasks", json=payload, timeout=15
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("task", result)
        except requests.RequestException as e:
            raise DevTrackerError(f"Failed to create task: {e}") from e

    def update_task(
        self,
        task_id: int,
        title: str | None = None,
        description: str | None = None,
        category: int | None = None,
        priority: str | None = None,
        effort: str | None = None,
    ) -> dict[str, object]:
        """Update an existing DevTracker task.

        Only sends non-None fields in the payload.

        Args:
            task_id: ID of the task to update.
            title: New task title (or None to leave unchanged).
            description: New task description (or None to leave unchanged).
            category: New category ID (or None to leave unchanged).
            priority: New priority level (or None to leave unchanged).
            effort: New effort level (or None to leave unchanged).

        Returns:
            Updated task dict from the API.

        Raises:
            DevTrackerError: If no fields to update or API call fails.
        """
        payload: dict[str, object] = {}
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if category is not None:
            payload["category"] = category
        if priority is not None:
            payload["priority"] = priority
        if effort is not None:
            payload["effort"] = effort

        if not payload:
            raise DevTrackerError("No fields to update")

        try:
            resp = self._session.patch(
                f"{self._base_url}/tasks/{task_id}", json=payload, timeout=15
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("task", result)
        except requests.RequestException as e:
            raise DevTrackerError(
                f"Failed to update task #{task_id}: {e}"
            ) from e

    def update_config(self, config: DevTrackerConfig) -> None:
        """Update client configuration (headers, URL). Invalidates category cache."""
        self._config = config
        self._session.headers.update(
            {
                "X-API-Key": config.api_key,
                "X-Developer-Email": config.email,
            }
        )
        self._categories = None
