"""Single agent implementation for simple task execution"""
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_agent
from langchain_core.tools import tool
from internal.agents.schemas import ImplementationResult
from internal.agents.model_factory import get_model
from internal.tools.workspace import WorkspaceTools
import json
import logging

logger = logging.getLogger(__name__)


class SingleAgent:
    """Simple single agent that handles all tasks using available tools"""

    def __init__(self, model_name: str = "qwen3.5:9b", mock_mode: bool = False, llm_provider: str = "ollama"):
        # Default to ollama with mock mode for testing
        if mock_mode:
            llm_provider = "fake"
        self.model = get_model(model_name=model_name, mock_mode=mock_mode, llm_provider=llm_provider)
        self.mock_mode = mock_mode
        self.llm_provider = llm_provider
    
    async def implement(
        self,
        task: str,
        implementation_plan: Dict[str, Any],
        repository_summary: Dict[str, Any],
        workspace_id: str,
        workspace_tools: WorkspaceTools,
        run_id: Optional[str] = None,
    ) -> ImplementationResult:
        """Implement the task using a single agent with all available tools"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a versatile software development agent. Your job is to implement the requested changes in a repository.

Follow these guidelines:
- Analyze the repository structure and understand the codebase
- Follow best practices for the detected language/framework
- Write clean, readable code with proper error handling
- Add appropriate tests when needed
- Use the available tools to read files, write files, and check git status
- Work through the task systematically
- Return a structured result with your implementation details"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Repository Summary:
{repository_summary}

Implement the changes. Use the available tools to:
1. Read existing files to understand the codebase
2. Write or modify files as needed
3. Check git status and diff to track changes

Return a structured result with:
- files_modified: List of files you modified
- files_created: List of files you created
- lines_added: Total lines added
- lines_removed: Total lines removed
- success: Whether implementation was successful
- errors: Any errors encountered
- warnings: Any warnings""")
        ])
        
        # Create tools for the agent
        @tool
        async def write_file(file_path: str, content: str) -> str:
            """Write a file to the workspace"""
            result = await workspace_tools.write_file(workspace_id, file_path, content)
            return json.dumps(result)
        
        @tool
        async def read_file(file_path: str) -> str:
            """Read a file from the workspace"""
            result = await workspace_tools.read_file(workspace_id, file_path)
            return json.dumps(result)
        
        @tool
        async def git_status() -> str:
            """Get git status"""
            result = await workspace_tools.git_status(workspace_id)
            return json.dumps(result)
        
        @tool
        async def git_diff() -> str:
            """Get git diff"""
            result = await workspace_tools.git_diff(workspace_id)
            return json.dumps(result)
        
        tools = [write_file, read_file, git_status, git_diff]
        
        # Create agent
        agent = create_agent(self.model, tools, system_prompt=prompt)
        # LangChain 0.3+ pattern - invoke agent directly
        try:
            result = await agent.ainvoke({
                "task": task,
                "implementation_plan": json.dumps(implementation_plan, indent=2),
                "repository_summary": json.dumps(repository_summary, indent=2),
            })
            
            return _parse_implementation_result(result)
            
        except Exception as e:
            logger.error(f"Single agent failed: {e}")
            return ImplementationResult(
                files_modified=[],
                files_created=[],
                lines_added=0,
                lines_removed=0,
                success=False,
                errors=[str(e)],
                warnings=[]
            )


def _parse_implementation_result(result: dict) -> ImplementationResult:
    """Parse an AgentExecutor result into an ImplementationResult"""
    files_created = []
    files_modified = []
    lines_added = 0
    lines_removed = 0
    errors = []
    warnings = []

    intermediate_steps = result.get("intermediate_steps", [])
    if intermediate_steps:
        for action, observation in intermediate_steps:
            try:
                tool_name = getattr(action, "tool", None)
                tool_input = getattr(action, "tool_input", None) or {}
                obs = json.loads(observation) if isinstance(observation, str) else observation
                if tool_name == "write_file" and obs.get("success"):
                    file_path = tool_input.get("file_path") or obs.get("file_path")
                    if file_path:
                        files_created.append(file_path)
                        content = tool_input.get("content", "")
                        lines_added += max(len(content.splitlines()), 1)
                elif tool_name == "git_diff":
                    diff_text = obs.get("diff", obs.get("output", ""))
                    if diff_text:
                        for line in diff_text.splitlines():
                            if line.startswith("+") and not line.startswith("+++"):
                                lines_added += 1
                            elif line.startswith("-") and not line.startswith("---"):
                                lines_removed += 1
            except Exception as e:
                logger.warning(f"Failed to parse intermediate step: {e}")

    output = result.get("output", "")
    success = not errors and (result.get("success") if isinstance(result, dict) else True)
    if not success:
        success = True  # default to success if no errors observed

    return ImplementationResult(
        files_modified=files_modified,
        files_created=files_created,
        lines_added=lines_added,
        lines_removed=lines_removed,
        success=success,
        errors=errors,
        warnings=warnings,
    )
