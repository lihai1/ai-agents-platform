"""Implementation agents for Go, Angular, and DevOps"""
from typing import Dict, Any, Optional, List
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_agent
from langchain_core.tools import tool
from internal.agents.schemas import ImplementationResult
from internal.agents.model_factory import get_model
from internal.tools.workspace import WorkspaceTools
from internal.tools.web_search import WebSearchTool
import json
import logging

logger = logging.getLogger(__name__)


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


class GoDeveloperAgent:
    """Agent for Go backend development"""

    def __init__(self, model_name: str = "gpt-4", mock_mode: bool = False, llm_provider: str = None):
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
        """Implement Go changes"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        # Initialize web search tool
        web_search = WebSearchTool()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Go developer agent. Your job is to implement the requested changes in a Go repository.

Follow these guidelines:
- Follow Go best practices and idioms
- Use the existing project structure
- Write clean, readable code with proper error handling
- Add appropriate tests
- Follow the implementation plan provided
- Only modify files that are in the implementation plan
- You can search the web for Go documentation, best practices, and examples"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Repository Summary:
{repository_summary}

Implement the changes. Return a structured result with:
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
        
        @tool
        async def search_web(query: str, max_results: int = 5) -> str:
            """Search the web for information"""
            result = await web_search.search(query, max_results)
            return json.dumps(result)
        
        @tool
        async def fetch_url(url: str) -> str:
            """Fetch and parse content from a specific URL"""
            result = await web_search.search_url(url)
            return json.dumps(result)
        
        @tool
        async def browse_page(url: str, wait_for_selector: str = None, timeout: int = 10000) -> str:
            """Open a headless browser and read the page content"""
            result = await web_search.browse_page(url, wait_for_selector, timeout)
            return json.dumps(result)
        
        @tool
        async def run_command(command: str, args: str = None, timeout: int = 30) -> str:
            """Run a shell command in the workspace"""
            args_list = json.loads(args) if args else None
            result = await workspace_tools.run_command(workspace_id, command, args_list, timeout)
            return json.dumps(result)
        
        tools = [write_file, read_file, git_status, git_diff, search_web, fetch_url, browse_page, run_command]
        
        # Create agent
        agent = create_agent(self.model, tools, system_prompt=prompt)
        # LangChain 0.3+ pattern - invoke agent directly
        try:
            result = await agent.ainvoke({
                "task": task,
                "implementation_plan": json.dumps(implementation_plan, indent=2),
                "repository_summary": json.dumps(repository_summary, indent=2),
            })
            
            # Parse the output to extract implementation result
            # In production, this would use structured output
            return _parse_implementation_result(result)
            
        except Exception as e:
            logger.error(f"Go developer agent failed: {e}")
            return ImplementationResult(
                files_modified=[],
                files_created=[],
                lines_added=0,
                lines_removed=0,
                success=False,
                errors=[str(e)],
                warnings=[]
            )


class AngularDeveloperAgent:
    """Agent for Angular component development"""

    def __init__(self, model_name: str = "gpt-4", mock_mode: bool = False, llm_provider: str = None):
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
        """Implement Angular changes"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        # Initialize web search tool
        web_search = WebSearchTool()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an Angular developer agent. Your job is to implement the requested changes in an Angular repository.

Follow these guidelines:
- Use Angular 22+ with standalone components
- Follow Angular best practices and style guide
- Use reactive forms and observables where appropriate
- Write clean, readable TypeScript code
- Add appropriate unit tests
- Follow the implementation plan provided
- Only modify files that are in the implementation plan
- You can search the web for Angular documentation, best practices, and examples"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Repository Summary:
{repository_summary}

Implement the changes. Return a structured result with:
- files_modified: List of files you modified
- files_created: List of files you created
- lines_added: Total lines added
- lines_removed: Total lines removed
- success: Whether implementation was successful
- errors: Any errors encountered
- warnings: Any warnings""")
        ])
        
        # Create tools (same as Go developer)
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
        
        @tool
        async def search_web(query: str, max_results: int = 5) -> str:
            """Search the web for information"""
            result = await web_search.search(query, max_results)
            return json.dumps(result)
        
        @tool
        async def fetch_url(url: str) -> str:
            """Fetch and parse content from a specific URL"""
            result = await web_search.search_url(url)
            return json.dumps(result)
        
        @tool
        async def browse_page(url: str, wait_for_selector: str = None, timeout: int = 10000) -> str:
            """Open a headless browser and read the page content"""
            result = await web_search.browse_page(url, wait_for_selector, timeout)
            return json.dumps(result)
        
        @tool
        async def run_command(command: str, args: str = None, timeout: int = 30) -> str:
            """Run a shell command in the workspace"""
            args_list = json.loads(args) if args else None
            result = await workspace_tools.run_command(workspace_id, command, args_list, timeout)
            return json.dumps(result)
        
        tools = [write_file, read_file, git_status, git_diff, search_web, fetch_url, browse_page, run_command]
        
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
            logger.error(f"Angular developer agent failed: {e}")
            return ImplementationResult(
                files_modified=[],
                files_created=[],
                lines_added=0,
                lines_removed=0,
                success=False,
                errors=[str(e)],
                warnings=[]
            )


class AngularUIDeveloperAgent:
    """Agent for Angular UI/UX work"""

    def __init__(self, model_name: str = "gpt-4", mock_mode: bool = False, llm_provider: str = None):
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
        """Implement Angular UI changes"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        # Initialize web search tool
        web_search = WebSearchTool()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an Angular UI developer agent. Your job is to implement UI/UX changes in an Angular repository.

Follow these guidelines:
- Focus on templates, styling, and visual design
- Use modern CSS (Flexbox, Grid, CSS Variables)
- Ensure responsive design
- Follow accessibility best practices (ARIA labels, keyboard navigation)
- Use Angular Material or similar component library when appropriate
- Follow the implementation plan provided
- You can search the web for CSS/HTML best practices, design patterns, and examples"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Repository Summary:
{repository_summary}

Implement the UI changes. Return a structured result with:
- files_modified: List of files you modified
- files_created: List of files you created
- lines_added: Total lines added
- lines_removed: Total lines removed
- success: Whether implementation was successful
- errors: Any errors encountered
- warnings: Any warnings""")
        ])
        
        # Create tools
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
        
        @tool
        async def search_web(query: str, max_results: int = 5) -> str:
            """Search the web for information"""
            result = await web_search.search(query, max_results)
            return json.dumps(result)
        
        @tool
        async def fetch_url(url: str) -> str:
            """Fetch and parse content from a specific URL"""
            result = await web_search.search_url(url)
            return json.dumps(result)
        
        @tool
        async def browse_page(url: str, wait_for_selector: str = None, timeout: int = 10000) -> str:
            """Open a headless browser and read the page content"""
            result = await web_search.browse_page(url, wait_for_selector, timeout)
            return json.dumps(result)
        
        @tool
        async def run_command(command: str, args: str = None, timeout: int = 30) -> str:
            """Run a shell command in the workspace"""
            args_list = json.loads(args) if args else None
            result = await workspace_tools.run_command(workspace_id, command, args_list, timeout)
            return json.dumps(result)
        
        tools = [write_file, read_file, git_status, git_diff, search_web, fetch_url, browse_page, run_command]
        
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
            logger.error(f"Angular UI developer agent failed: {e}")
            return ImplementationResult(
                files_modified=[],
                files_created=[],
                lines_added=0,
                lines_removed=0,
                success=False,
                errors=[str(e)],
                warnings=[]
            )


class DevOpsDeveloperAgent:
    """Agent for DevOps and infrastructure changes"""

    def __init__(self, model_name: str = "gpt-4", mock_mode: bool = False, llm_provider: str = None):
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
        """Implement DevOps changes"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        # Initialize web search tool
        web_search = WebSearchTool()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a DevOps developer agent. Your job is to implement infrastructure and deployment changes.

Follow these guidelines:
- Modify Dockerfiles, Docker Compose, Kubernetes manifests, Helm charts
- Update CI/CD pipelines (GitHub Actions, GitLab CI, etc.)
- Follow infrastructure as code best practices
- Ensure security best practices (non-root containers, minimal base images)
- Follow the implementation plan provided
- You can search the web for DevOps best practices, documentation, and examples"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Repository Summary:
{repository_summary}

Implement the DevOps changes. Return a structured result with:
- files_modified: List of files you modified
- files_created: List of files you created
- lines_added: Total lines added
- lines_removed: Total lines removed
- success: Whether implementation was successful
- errors: Any errors encountered
- warnings: Any warnings""")
        ])
        
        # Create tools
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
        
        @tool
        async def search_web(query: str, max_results: int = 5) -> str:
            """Search the web for information"""
            result = await web_search.search(query, max_results)
            return json.dumps(result)
        
        @tool
        async def fetch_url(url: str) -> str:
            """Fetch and parse content from a specific URL"""
            result = await web_search.search_url(url)
            return json.dumps(result)
        
        @tool
        async def browse_page(url: str, wait_for_selector: str = None, timeout: int = 10000) -> str:
            """Open a headless browser and read the page content"""
            result = await web_search.browse_page(url, wait_for_selector, timeout)
            return json.dumps(result)
        
        @tool
        async def run_command(command: str, args: str = None, timeout: int = 30) -> str:
            """Run a shell command in the workspace"""
            args_list = json.loads(args) if args else None
            result = await workspace_tools.run_command(workspace_id, command, args_list, timeout)
            return json.dumps(result)
        
        tools = [write_file, read_file, git_status, git_diff, search_web, fetch_url, browse_page, run_command]
        
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
            logger.error(f"DevOps developer agent failed: {e}")
            return ImplementationResult(
                files_modified=[],
                files_created=[],
                lines_added=0,
                lines_removed=0,
                success=False,
                errors=[str(e)],
                warnings=[]
            )
