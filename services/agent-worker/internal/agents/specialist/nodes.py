"""Specialist agent workflow nodes"""
import asyncio
from datetime import datetime
from typing import Dict, Any
from internal.workflow.state import EngineeringState
from internal.messaging.nats import get_nats_client
from internal.tools.workspace import WorkspaceTools
from .implementers import GoDeveloperAgent, AngularDeveloperAgent, AngularUIDeveloperAgent, DevOpsDeveloperAgent
import logging

logger = logging.getLogger(__name__)


def _workspace_tools(state: EngineeringState) -> WorkspaceTools:
    """Create a WorkspaceTools instance for the current run"""
    return WorkspaceTools(
        run_id=state.get("run_id"),
        user_id=state.get("user_id"),
        workspace_path=state.get("workspace_id") or "/workspace",
    )


async def publish_state_event(run_id: str, user_id: str, event_type: str, payload: dict = None):
    """Publish state change event to NATS"""
    try:
        nats = get_nats_client()
        if nats is None:
            logger.warning("NATS client not available, skipping state event")
            return
        if nats.js is None:
            await nats.connect()
        await nats.publish_event(
            event_type=event_type,
            run_id=run_id,
            user_id=user_id,
            payload=payload or {}
        )
        logger.info(f"Published state event: {event_type} for run {run_id}")
    except Exception as e:
        logger.error(f"Failed to publish state event: {e}")


async def publish_chat_event(run_id: str, user_id: str, event_type: str, payload: dict = None):
    """Publish progress/final event to agent.user.{user_id}.chat.{run_id}.events"""
    try:
        nats = get_nats_client()
        if nats is None:
            logger.warning("NATS client not available, skipping chat event")
            return
        if nats.js is None:
            await nats.connect()

        await nats.publish_chat_event(
            event_type=event_type,
            run_id=run_id,
            user_id=user_id,
            payload=payload or {}
        )
        logger.info(f"Published chat event: {event_type} for run {run_id}")
    except Exception as e:
        logger.error(f"Failed to publish chat event: {e}")


def _pydantic_to_dict(value):
    """Convert a Pydantic model or dict to a plain dict"""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _get_implementation_agent(agent_name: str, mock_mode: bool, llm_provider: str):
    """Instantiate the appropriate implementation agent based on agent name"""
    if agent_name in ("go-developer", "backend-developer", "developer"):
        return GoDeveloperAgent(mock_mode=mock_mode, llm_provider=llm_provider)
    elif agent_name == "angular-developer":
        return AngularDeveloperAgent(mock_mode=mock_mode, llm_provider=llm_provider)
    elif agent_name == "angular-ui-developer":
        return AngularUIDeveloperAgent(mock_mode=mock_mode, llm_provider=llm_provider)
    elif agent_name == "devops-developer":
        return DevOpsDeveloperAgent(mock_mode=mock_mode, llm_provider=llm_provider)
    return None


def _aggregate_implementation_results(results: list) -> dict:
    """Aggregate results from multiple implementation agents into a single summary"""
    success = all(r.get("success", False) for r in results)
    files_modified = []
    files_created = []
    lines_added = 0
    lines_removed = 0
    errors = []
    warnings = []
    
    for r in results:
        files_modified.extend(r.get("files_modified", []) or [])
        files_created.extend(r.get("files_created", []) or [])
        lines_added += r.get("lines_added", 0) or 0
        lines_removed += r.get("lines_removed", 0) or 0
        errors.extend(r.get("errors", []) or [])
        warnings.extend(r.get("warnings", []) or [])

    return {
        "files_modified": files_modified,
        "files_created": files_created,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "success": success,
        "errors": errors,
        "warnings": warnings,
    }


def _get_default_implementation_results() -> dict:
    """Return default implementation results when no agents are selected"""
    return {
        "files_modified": [],
        "files_created": [],
        "lines_added": 0,
        "lines_removed": 0,
        "success": False,
        "errors": ["No implementation agents were selected"],
        "warnings": [],
    }


def _get_error_implementation_results(error: str) -> dict:
    """Return error implementation results when implementation fails"""
    return {
        "files_modified": [],
        "files_created": [],
        "lines_added": 0,
        "lines_removed": 0,
        "success": False,
        "errors": [error],
        "warnings": [],
    }


async def _capture_code_diff(workspace_tools: WorkspaceTools, workspace_id: str) -> str:
    """Capture git diff for review, returning empty string on failure"""
    try:
        diff = await workspace_tools.git_diff(workspace_id)
        return diff.get("diff", diff.get("output", ""))
    except Exception as e:
        logger.error(f"Failed to capture diff: {e}")
        return ""


async def implementing_specialist_node(state: EngineeringState) -> EngineeringState:
    """Implement changes using specialist agents"""
    state["status"] = "IMPLEMENTING"
    state["current_phase"] = "IMPLEMENTING"
    
    await publish_state_event(state["run_id"], state["user_id"], "implementing", {"status": "IMPLEMENTING"})

    mock_mode = state.get("mock_mode", False)
    llm_provider = state.get("llm_provider")
    task = state.get("task", "")
    implementation_plan = state.get("implementation_plan") or {}
    repository_summary = state.get("repository_summary") or {}
    selected_agents = state.get("selected_agents") or []
    workspace_id = state.get("workspace_id") or "/workspace"
    workspace_tools = _workspace_tools(state)

    logger.info(f"Using specialist agents: {selected_agents}")

    try:
        results = []
        for agent_name in selected_agents:
            agent = _get_implementation_agent(agent_name, mock_mode, llm_provider)
            if agent is None:
                logger.warning(f"Unknown implementation agent: {agent_name}, skipping")
                continue

            result = await agent.implement(
                task=task,
                implementation_plan=implementation_plan,
                repository_summary=repository_summary,
                workspace_id=workspace_id,
                workspace_tools=workspace_tools,
                run_id=state["run_id"],
            )
            results.append(_pydantic_to_dict(result))

        if results:
            state["implementation_results"] = _aggregate_implementation_results(results)
        else:
            state["implementation_results"] = _get_default_implementation_results()
            
        state["code_diff"] = await _capture_code_diff(workspace_tools, workspace_id)
        
    except Exception as e:
        logger.error(f"Specialist agent implementation failed: {e}")
        state["implementation_results"] = _get_error_implementation_results(str(e))
        state["code_diff"] = ""

    return state
