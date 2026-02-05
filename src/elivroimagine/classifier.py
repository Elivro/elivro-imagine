"""Task classification and translation using Berget AI (Mistral)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

API_URL = "https://api.berget.ai/v1/chat/completions"
MODEL = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"

VALID_PRIORITIES = ["low", "medium", "high", "critical"]
VALID_EFFORTS = ["tiny", "small", "medium", "large", "massive"]

SYSTEM_PROMPT_TEMPLATE = """\
You are a task classifier for a software development project.

Given a voice transcription from a developer, extract a structured task.

IMPORTANT LANGUAGE RULE: If the input is in Swedish or any non-English language, \
translate it to English first. ALL output fields (title, description) MUST be in English.

Categories (pick the BEST match from this list):
{categories}

Priority:
- low: Nice to have, no deadline
- medium: Should be done soon, normal workflow
- high: Blocking other work or user-facing issue
- critical: Production bug or security issue

Effort:
- tiny: < 1 hour (typo fix, config change)
- small: 1-4 hours (simple feature, bug fix)
- medium: 4-16 hours (feature with multiple components)
- large: 2-5 days (complex feature, refactoring)
- massive: > 1 week (major system change)

Rules:
- Title: imperative form, under 60 characters (e.g. "Fix login button on mobile")
- Description: 1-3 sentences explaining the task
- Category MUST be one of the exact names listed above
- Respond with JSON ONLY, no markdown fences, no explanation

JSON format:
{{"title": "...", "description": "...", "category": "...", "priority": "...", "effort": "..."}}
"""


class ClassificationError(Exception):
    """Raised when task classification fails."""

    pass


@dataclass
class TaskClassification:
    """Result of classifying a transcription into a task."""

    title: str
    description: str
    category: str
    priority: str
    effort: str


def _fuzzy_match_category(name: str, valid_categories: list[str]) -> str:
    """Try to match an unknown category name to a valid one.

    Falls back to the first category if no match found.
    """
    name_lower = name.lower()
    for cat in valid_categories:
        if cat.lower() in name_lower or name_lower in cat.lower():
            return cat
    return valid_categories[0] if valid_categories else name


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from response text."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```\w*\s*", "", text)
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _build_system_prompt(categories: list[str]) -> str:
    """Build the system prompt with the given category list."""
    category_lines = "\n".join(f"- {cat}" for cat in categories)
    return SYSTEM_PROMPT_TEMPLATE.format(categories=category_lines)


def classify_transcription(
    text: str, api_key: str, categories: list[str] | None = None
) -> TaskClassification:
    """Classify a transcription into a structured task using Mistral.

    Args:
        text: The transcribed text to classify.
        api_key: Berget AI API key.
        categories: List of valid category names from the project.
            If None, the LLM picks freely (no category validation).

    Returns:
        TaskClassification with title, description, category, priority, effort.

    Raises:
        ClassificationError: If the API call or parsing fails.
    """
    system_prompt = _build_system_prompt(categories or ["General"])

    try:
        resp = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise ClassificationError(f"API request failed: {e}") from e

    if resp.status_code != 200:
        raise ClassificationError(f"API error {resp.status_code}: {resp.text[:200]}")

    try:
        api_result = resp.json()
        content = api_result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise ClassificationError(f"Unexpected API response format: {e}") from e

    content = _strip_markdown_fences(content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ClassificationError(
            f"Failed to parse classification JSON: {e}. Raw: {content[:200]}"
        ) from e

    title = str(parsed.get("title", "Untitled task"))
    description = str(parsed.get("description", ""))
    category = str(parsed.get("category", ""))
    priority = str(parsed.get("priority", "medium")).lower()
    effort = str(parsed.get("effort", "medium")).lower()

    # Validate and fix category against the provided list
    if categories and category not in categories:
        category = _fuzzy_match_category(category, categories)

    # Validate priority and effort
    if priority not in VALID_PRIORITIES:
        priority = "medium"
    if effort not in VALID_EFFORTS:
        effort = "medium"

    return TaskClassification(
        title=title,
        description=description,
        category=category,
        priority=priority,
        effort=effort,
    )
