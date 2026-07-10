"""Workflow graph factory for different agent types"""
from typing import Dict, Any
from langgraph.checkpoint.memory import MemorySaver
from internal.workflow.state import EngineeringState
from internal.workflow.single_agent_graph import create_single_agent_run
from internal.workflow.specialist_agent_graph import create_specialist_agent_run
import os


async def create_run(state: EngineeringState, checkpointer: MemorySaver) -> Dict[str, Any]:
    """Factory function to create and start a run with the appropriate workflow graph"""
    agent_type = state.get("agent_type") or os.environ.get("AGENT_TYPE", "specialist")
    
    if agent_type == "single-agent":
        return await create_single_agent_run(state, checkpointer)
    else:
        return await create_specialist_agent_run(state, checkpointer)
