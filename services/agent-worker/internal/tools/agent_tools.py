"""Shared tool creation functions for agent workers."""
from __future__ import annotations

import json
from typing import Optional, List, Dict, Any, Callable

from langchain_core.tools import tool
from internal.tools.workspace import WorkspaceTools
from internal.tools.web_search import WebSearchTool
from internal.tools.repository import ReadOnlyRepositoryTools, RepositoryMetadataTools


def create_workspace_tools(
    workspace_id: str,
    workspace_tools: WorkspaceTools,
    include_read: bool = True,
    include_write: bool = True,
    include_list: bool = True,
    include_git_status: bool = True,
    include_git_diff: bool = True,
    include_run_tests: bool = False,
    include_run_command: bool = False,
    include_apply_patch: bool = False,
) -> List[Callable]:
    """Create workspace tools with configurable inclusion."""
    tools = []

    if include_read:
        @tool
        async def read_file(file_path: str) -> str:
            """Read a file from the workspace"""
            result = await workspace_tools.read_file(workspace_id, file_path)
            return json.dumps(result)
        tools.append(read_file)

    if include_write:
        @tool
        async def write_file(file_path: str, content: str) -> str:
            """Write a file to the workspace"""
            result = await workspace_tools.write_file(workspace_id, file_path, content)
            return json.dumps(result)
        tools.append(write_file)

    if include_list:
        @tool
        async def list_files(directory: str = ".") -> str:
            """List files in a directory"""
            result = await workspace_tools.list_files(workspace_id, directory)
            return json.dumps(result)
        tools.append(list_files)

    if include_git_status:
        @tool
        async def git_status() -> str:
            """Get git status"""
            result = await workspace_tools.git_status(workspace_id)
            return json.dumps(result)
        tools.append(git_status)

    if include_git_diff:
        @tool
        async def git_diff() -> str:
            """Get git diff"""
            result = await workspace_tools.git_diff(workspace_id)
            return json.dumps(result)
        tools.append(git_diff)

    if include_run_tests:
        @tool
        async def run_tests(test_command: Optional[str] = None) -> str:
            """Run tests in the workspace"""
            command = json.loads(test_command) if test_command else None
            result = await workspace_tools.run_tests(workspace_id, command)
            return json.dumps(result)
        tools.append(run_tests)

    if include_run_command:
        @tool
        async def run_command(command: str, command_args: Optional[str] = None, timeout: int = 30) -> str:
            """Run a shell command in the workspace"""
            args_list = json.loads(command_args) if command_args else None
            result = await workspace_tools.run_command(workspace_id, command, args_list, timeout)
            return json.dumps(result)
        tools.append(run_command)

    if include_apply_patch:
        @tool
        async def apply_patch(patch_content: str) -> str:
            """Apply a patch to the workspace"""
            result = await workspace_tools.apply_patch(workspace_id, patch_content)
            return json.dumps(result)
        tools.append(apply_patch)

    return tools


def create_web_search_tools() -> List[Callable]:
    """Create web search tools."""
    web_search = WebSearchTool()
    tools = []

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
    async def browse_page(url: str, wait_for_selector: Optional[str] = None, timeout: int = 10000) -> str:
        """Open a headless browser and read the page content"""
        result = await web_search.browse_page(url, wait_for_selector, timeout)
        return json.dumps(result)

    tools.extend([search_web, fetch_url, browse_page])
    return tools


def create_repository_tools(repository_path: str) -> List[Callable]:
    """Create read-only repository tools."""
    repo_tools = ReadOnlyRepositoryTools(repository_path)
    tools = []

    @tool
    def list_files(pattern: str = "*", recursive: bool = True) -> List[str]:
        """List files in the repository matching a pattern"""
        return repo_tools.list_files(pattern, recursive)

    @tool
    def read_file(file_path: str) -> str:
        """Read a file's contents"""
        return repo_tools.read_file(file_path)

    @tool
    def search_files(pattern: str, file_pattern: str = "*") -> List[Dict[str, Any]]:
        """Search for a pattern in files"""
        return repo_tools.search_files(pattern, file_pattern)

    @tool
    def get_directory_structure(max_depth: int = 3) -> Dict[str, Any]:
        """Get simplified directory structure"""
        return repo_tools.get_directory_structure(max_depth)

    tools.extend([list_files, read_file, search_files, get_directory_structure])
    return tools


def create_repository_metadata_tools(
    control_plane_base_url: str,
    http_client,
    repository_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> List[Callable]:
    """Create repository metadata tools."""
    metadata_tools = RepositoryMetadataTools(control_plane_base_url, http_client)
    tools = []

    if repository_id:
        @tool
        async def get_repository_metadata() -> Dict[str, Any]:
            """Get repository metadata from control plane"""
            return await metadata_tools.get_repository_metadata(repository_id)
        tools.append(get_repository_metadata)

    if project_id:
        @tool
        async def get_project_metadata() -> Dict[str, Any]:
            """Get project metadata from control plane"""
            return await metadata_tools.get_project_metadata(project_id)
        tools.append(get_project_metadata)

    return tools
