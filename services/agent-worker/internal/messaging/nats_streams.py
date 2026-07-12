"""Shared NATS JetStream stream configurations."""
from __future__ import annotations

from typing import List, Dict, Any


def get_default_stream_configs() -> List[Dict[str, Any]]:
    """Get default NATS JetStream stream configurations."""
    return [
        {
            "name": "AGENT_CHAT",
            "subjects": ["agent.user.*.chat.>"],
            "description": "Agent chat stream for user events",
            "retention": "limits",
            "max_age": 86400,
            "storage": "file",
        },
        {
            "name": "AGENT_CONTROL",
            "subjects": ["agent.control.>"],
            "description": "Agent control stream",
            "retention": "limits",
            "max_age": 86400,
            "storage": "file",
        },
        {
            "name": "AGENT_EVENTS",
            "subjects": ["agent.user.*.events.>"],
            "description": "Agent event stream",
            "retention": "limits",
            "max_age": 86400,
            "storage": "file",
        },
        {
            "name": "AGENT_ERRORS",
            "subjects": ["agent.user.*.chat.errors"],
            "description": "Agent error stream",
            "retention": "limits",
            "max_age": 86400,
            "storage": "file",
        },
    ]


def get_crewai_stream_configs() -> List[Dict[str, Any]]:
    """Get CrewAI-specific NATS JetStream stream configurations."""
    return [
        {
            "name": "AGENT_CHAT",
            "subjects": ["agent.user.*.chat.>"],
            "description": "Agent chat stream for user events",
            "retention": "limits",
            "max_age": 86400,
            "storage": "file",
        },
        {
            "name": "AGENT_CONTROL",
            "subjects": ["agent.control.>"],
            "description": "Agent control stream",
            "retention": "limits",
            "max_age": 86400,
            "storage": "file",
        },
        {
            "name": "AGENT_EVENTS",
            "subjects": ["agent.user.*.events.>"],
            "description": "Agent event stream",
            "retention": "limits",
            "max_age": 86400,
            "storage": "file",
        },
    ]
