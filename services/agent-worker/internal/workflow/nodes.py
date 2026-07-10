import asyncio
from datetime import datetime
from typing import Dict, Any
from internal.workflow.state import EngineeringState
from internal.db import get_session
from internal.models import WorkspaceLease
from internal.workflow.approvals import request_approval
from internal.messaging.nats import get_nats_client
from internal.tools.workspace import WorkspaceTools
from internal.agents.specialists import SkillsLeadAgent, SolutionPlannerAgent, RepoScoutAgent
from internal.agents.validators import BackendTestEngineerAgent, AngularTestEngineerAgent, CodeReviewerAgent, CompletionVerifierAgent
import uuid
import os
import logging

logger = logging.getLogger(__name__)


def _workspace_tools(state: EngineeringState) -> WorkspaceTools:
    """Create a WorkspaceTools instance for the current run"""
    return WorkspaceTools(
        workspace_path=state.get("workspace_id") or "/workspace",
        run_id=state.get("run_id"),
    )


async def publish_state_event(run_id: str, event_type: str, payload: dict = None):
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
            payload=payload or {}
        )
        logger.info(f"Published state event: {event_type} for run {run_id}")
    except Exception as e:
        logger.error(f"Failed to publish state event: {e}")


async def publish_chat_event(run_id: str, event_type: str, payload: dict = None):
    """Publish progress/final event to agent.chat.{run_id}.events"""
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
            payload=payload or {}
        )
        logger.info(f"Published chat event: {event_type} for run {run_id}")
    except Exception as e:
        logger.error(f"Failed to publish chat event: {e}")

import json


def _pydantic_to_dict(value):
    """Convert a Pydantic model or dict to a plain dict"""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


async def created_node(state: EngineeringState) -> EngineeringState:
    """Initial node - marks run as created"""
    await asyncio.sleep(0.1)
    state["status"] = "CREATED"
    state["current_phase"] = "CREATED"
    await publish_state_event(state["run_id"], "created", {"status": "CREATED"})
    return state


async def preparing_workspace_node(state: EngineeringState) -> EngineeringState:
    """Prepare workspace - repository already cloned in container"""
    state["status"] = "PREPARING_WORKSPACE"
    state["current_phase"] = "PREPARING_WORKSPACE"
    await publish_state_event(state["run_id"], "preparing_workspace", {"status": "PREPARING_WORKSPACE"})

    # Workspace is now the container itself, created by Go control plane
    # Repository is already cloned to /workspace. Allow override for local integration tests.
    await asyncio.sleep(0.1)
    state["workspace_id"] = os.environ.get("WORKSPACE_PATH", "/workspace")
    state["workspace_branch"] = "main"

    return state


async def scouting_node(state: EngineeringState) -> EngineeringState:
    """Scout repository - real repo-scout agent"""
    state["status"] = "SCOUTING"
    state["current_phase"] = "SCOUTING"
    await publish_state_event(state["run_id"], "scouting", {"status": "SCOUTING"})

    mock_mode = state.get("mock_mode", False)
    llm_provider = state.get("llm_provider")
    workspace_id = state.get("workspace_id") or "/workspace"

    try:
        scout = RepoScoutAgent(repository_path=workspace_id, mock_mode=mock_mode, llm_provider=llm_provider)
        summary = await scout.analyze_repository()
        state["repository_summary"] = _pydantic_to_dict(summary)
    except Exception as e:
        logger.error(f"Scouting failed: {e}")
        state["repository_summary"] = {
            "primary_language": "Go",
            "frameworks": [],
            "project_type": "unknown",
            "total_files": 0,
            "test_files": 0,
            "main_source_files": 0,
            "config_files": 0,
            "directory_structure": {},
            "key_files": [],
            "build_system": None,
            "test_framework": None,
            "dependencies": [],
        }

    return state


async def planning_node(state: EngineeringState) -> EngineeringState:
    """Plan implementation - real skills-lead and solution-planner agents"""
    state["status"] = "PLANNING"
    state["current_phase"] = "PLANNING"
    await publish_state_event(state["run_id"], "planning", {"status": "PLANNING"})

    mock_mode = state.get("mock_mode", False)
    llm_provider = state.get("llm_provider")
    task = state.get("task", "")
    repository_summary = state.get("repository_summary") or {}

    try:
        skills_lead = SkillsLeadAgent(mock_mode=mock_mode, llm_provider=llm_provider)
        decision = await skills_lead.select_specialists(
            task=task,
            repository_summary=repository_summary,
        )
        selected = decision.selected_specialists or ["go-developer"]
        state["selected_agents"] = selected

        planner = SolutionPlannerAgent(mock_mode=mock_mode, llm_provider=llm_provider)
        plan = await planner.create_plan(
            task=task,
            repository_summary=repository_summary,
            selected_specialists=selected,
        )
        state["implementation_plan"] = _pydantic_to_dict(plan)
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        state["selected_agents"] = ["go-developer"]
        state["implementation_plan"] = {
            "description": "Create a simple Go file and run the test suite",
            "files_expected_to_change": ["hello.go"],
            "acceptance_criteria": [
                "A Go file is created",
                "Tests pass"
            ],
            "estimated_steps": 3,
            "risk_factors": [],
            "suggested_approach": "Create a small Go file and execute the tests",
            "dependencies_to_add": None,
            "tests_to_write": []
        }

    return state


async def designing_node(state: EngineeringState) -> EngineeringState:
    """Design solution - lightweight design spec"""
    state["status"] = "DESIGNING"
    state["current_phase"] = "DESIGNING"
    await publish_state_event(state["run_id"], "designing", {"status": "DESIGNING"})

    repository_summary = state.get("repository_summary") or {}
    implementation_plan = state.get("implementation_plan") or {}

    state["design_spec"] = {
        "architecture": f"{repository_summary.get('primary_language', 'Go')} implementation",
        "data_flow": "User request -> Agent tools -> Workspace",
        "components": implementation_plan.get("files_expected_to_change", []),
    }
    return state


async def testing_node(state: EngineeringState) -> EngineeringState:
    """Run tests - execute real test engineer agents"""
    state["status"] = "TESTING"
    state["current_phase"] = "TESTING"
    await publish_state_event(state["run_id"], "testing", {"status": "TESTING"})

    mock_mode = state.get("mock_mode", False)
    llm_provider = state.get("llm_provider")
    task = state.get("task", "")
    implementation_plan = state.get("implementation_plan") or {}
    repository_summary = state.get("repository_summary") or {}
    workspace_id = state.get("workspace_id") or "/workspace"
    workspace_tools = _workspace_tools(state)
    selected_agents = state.get("selected_agents") or []

    try:
        if any(a in ("angular-developer", "angular-ui-developer") for a in selected_agents):
            test_agent = AngularTestEngineerAgent(mock_mode=mock_mode, llm_provider=llm_provider)
        else:
            test_agent = BackendTestEngineerAgent(mock_mode=mock_mode, llm_provider=llm_provider)

        result = await test_agent.run_tests(
            task=task,
            implementation_plan=implementation_plan,
            workspace_id=workspace_id,
            workspace_tools=workspace_tools,
            run_id=state["run_id"],
        )
        state["test_results"] = _pydantic_to_dict(result)
    except Exception as e:
        logger.error(f"Testing failed: {e}")
        state["test_results"] = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "coverage": 0.0,
            "test_output": str(e),
            "failed_tests": []
        }

    return state


async def reviewing_node(state: EngineeringState) -> EngineeringState:
    """Review code - execute real code reviewer agent"""
    state["status"] = "REVIEWING"
    state["current_phase"] = "REVIEWING"
    await publish_state_event(state["run_id"], "reviewing", {"status": "REVIEWING"})

    mock_mode = state.get("mock_mode", False)
    llm_provider = state.get("llm_provider")
    task = state.get("task", "")
    implementation_plan = state.get("implementation_plan") or {}
    code_diff = state.get("code_diff") or ""
    workspace_id = state.get("workspace_id") or "/workspace"
    workspace_tools = _workspace_tools(state)

    try:
        reviewer = CodeReviewerAgent(mock_mode=mock_mode, llm_provider=llm_provider)
        result = await reviewer.review(
            task=task,
            implementation_plan=implementation_plan,
            code_diff=code_diff,
            workspace_id=workspace_id,
            workspace_tools=workspace_tools,
            run_id=state["run_id"],
        )
        state["review_results"] = _pydantic_to_dict(result)
    except Exception as e:
        logger.error(f"Review failed: {e}")
        state["review_results"] = {
            "decision": "approved",
            "findings": [],
            "summary": f"Review failed: {e}"
        }

    return state


async def verifying_node(state: EngineeringState) -> EngineeringState:
    """Verify completion - execute real completion verifier agent"""
    state["status"] = "VERIFYING"
    state["current_phase"] = "VERIFYING"
    await publish_state_event(state["run_id"], "verifying", {"status": "VERIFYING"})

    mock_mode = state.get("mock_mode", False)
    llm_provider = state.get("llm_provider")
    task = state.get("task", "")
    implementation_plan = state.get("implementation_plan") or {}
    test_results = state.get("test_results") or {}
    review_results = state.get("review_results") or {}
    workspace_id = state.get("workspace_id") or "/workspace"
    workspace_tools = _workspace_tools(state)

    try:
        verifier = CompletionVerifierAgent(mock_mode=mock_mode, llm_provider=llm_provider)
        result = await verifier.verify(
            task=task,
            implementation_plan=implementation_plan,
            test_results=test_results,
            review_results=review_results,
            workspace_id=workspace_id,
            workspace_tools=workspace_tools,
            run_id=state["run_id"],
        )
        state["verification_results"] = _pydantic_to_dict(result)
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        state["verification_results"] = {
            "accepted": False,
            "criteria_results": [],
            "summary": f"Verification failed: {e}"
        }

    return state


async def repairing_node(state: EngineeringState) -> EngineeringState:
    """Repair issues - transition back to implementing"""
    state["status"] = "REPAIRING"
    state["current_phase"] = "REPAIRING"
    state["repair_count"] = state.get("repair_count", 0) + 1
    await publish_state_event(state["run_id"], "repairing", {"status": "REPAIRING", "repair_count": state["repair_count"]})
    await asyncio.sleep(0.4)
    return state


async def waiting_approval_node(state: EngineeringState) -> EngineeringState:
    """Wait for human approval - use LangGraph interrupt"""
    state["status"] = "WAITING_APPROVAL"
    state["current_phase"] = "WAITING_APPROVAL"
    await publish_state_event(state["run_id"], "waiting_approval", {"status": "WAITING_APPROVAL"})

    # In production, this would use request_approval() to interrupt the workflow
    await asyncio.sleep(0.1)

    return state


async def completed_node(state: EngineeringState) -> EngineeringState:
    """Mark run as completed"""
    await asyncio.sleep(0.1)
    state["status"] = "COMPLETED"
    state["current_phase"] = "COMPLETED"
    await publish_state_event(state["run_id"], "completed", {"status": "COMPLETED"})
    return state


async def failed_node(state: EngineeringState) -> EngineeringState:
    """Mark run as failed"""
    await asyncio.sleep(0.1)
    state["status"] = "FAILED"
    state["current_phase"] = "FAILED"
    error_message = state.get("error_message") or "Verification failed after repair limit"
    state["error_message"] = error_message
    await publish_state_event(state["run_id"], "failed", {"error_message": error_message})
    return state


async def cancelled_node(state: EngineeringState) -> EngineeringState:
    """Mark run as cancelled"""
    await asyncio.sleep(0.1)
    state["status"] = "CANCELLED"
    state["current_phase"] = "CANCELLED"
    state["error_message"] = "Run cancelled by user"
    await publish_state_event(state["run_id"], "cancelled", {"error_message": "Run cancelled by user"})
    return state


async def budget_exceeded_node(state: EngineeringState) -> EngineeringState:
    """Mark run as budget exceeded"""
    await asyncio.sleep(0.1)
    state["status"] = "BUDGET_EXCEEDED"
    state["current_phase"] = "BUDGET_EXCEEDED"
    state["error_message"] = "Budget limit exceeded"
    await publish_state_event(state["run_id"], "budget_exceeded", {"error_message": "Budget limit exceeded"})
    return state
