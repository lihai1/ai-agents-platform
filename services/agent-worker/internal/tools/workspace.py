"""Workspace tools for file operations in container workspace"""
from typing import Dict, Any, List, Optional
import logging
import os
import subprocess
import asyncio
import json
import uuid
from datetime import datetime
from internal.messaging.nats import get_nats_client

logger = logging.getLogger(__name__)


class WorkspaceTools:
    """Tools for interacting with the container workspace (local file system)"""
    
    def __init__(self, workspace_path: str = "/workspace", run_id: Optional[str] = None):
        self.workspace_path = workspace_path
        self.run_id = run_id
    
    async def _publish_tool_event(self, tool_name: str, action: str, details: Dict[str, Any]):
        """Publish tool execution event to NATS"""
        if not self.run_id:
            return
        
        try:
            nats = get_nats_client()
            if nats.js is None:
                await nats.connect()
            if not nats.js:
                return
            
            # Publish to agent.events.{run_id}.tool.executed
            event = {
                "message_id": str(uuid.uuid4()),
                "event_type": "tool.executed",
                "run_id": self.run_id,
                "payload": {
                    "tool": tool_name,
                    "action": action,
                    "details": details,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "timestamp": datetime.utcnow().isoformat(),
                "schema_version": "1.0",
            }
            
            subject = f"agent.events.{self.run_id}.tool.executed"
            await nats.js.publish(
                subject=subject,
                payload=json.dumps(event).encode(),
                headers={"run_id": self.run_id}
            )
            logger.info(f"[WORKSPACE] Published tool event: {tool_name} - {action}")
        except Exception as e:
            logger.error(f"[WORKSPACE] Failed to publish tool event: {e}")
    
    async def write_file(
        self,
        workspace_id: str,
        file_path: str,
        content: str,
    ) -> Dict[str, Any]:
        """Write a file to the workspace"""
        try:
            full_path = os.path.join(self.workspace_path, file_path.lstrip("/"))
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, "w") as f:
                f.write(content)
            
            await self._publish_tool_event("write_file", "write", {"file_path": file_path})
            
            return {
                "success": True,
                "file_path": file_path,
                "message": f"Successfully wrote {file_path}"
            }
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            await self._publish_tool_event("write_file", "error", {"file_path": file_path, "error": str(e)})
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e)
            }
    
    async def read_file(
        self,
        workspace_id: str,
        file_path: str,
    ) -> Dict[str, Any]:
        """Read a file from the workspace"""
        try:
            full_path = os.path.join(self.workspace_path, file_path.lstrip("/"))
            
            with open(full_path, "r") as f:
                content = f.read()
            
            await self._publish_tool_event("read_file", "read", {"file_path": file_path})
            
            return {
                "success": True,
                "file_path": file_path,
                "content": content
            }
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            await self._publish_tool_event("read_file", "error", {"file_path": file_path, "error": str(e)})
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e)
            }
    
    async def apply_patch(
        self,
        workspace_id: str,
        patch_content: str,
    ) -> Dict[str, Any]:
        """Apply a patch to the workspace"""
        try:
            # Write patch to temp file
            patch_path = "/tmp/changes.patch"
            with open(patch_path, "w") as f:
                f.write(patch_content)
            
            # Apply patch using subprocess
            proc = await asyncio.create_subprocess_exec(
                "git", "apply", patch_path,
                cwd=self.workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            await self._publish_tool_event("apply_patch", "apply", {"exit_code": proc.returncode})
            
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "output": stdout.decode(),
                "error": stderr.decode()
            }
        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            await self._publish_tool_event("apply_patch", "error", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    async def git_status(
        self,
        workspace_id: str,
    ) -> Dict[str, Any]:
        """Get git status from workspace"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain",
                cwd=self.workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            await self._publish_tool_event("git_status", "status", {"exit_code": proc.returncode})
            
            return {
                "success": True,
                "status": stdout.decode()
            }
        except Exception as e:
            logger.error(f"Failed to get git status: {e}")
            await self._publish_tool_event("git_status", "error", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    async def git_diff(
        self,
        workspace_id: str,
    ) -> Dict[str, Any]:
        """Get git diff from workspace"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff",
                cwd=self.workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            await self._publish_tool_event("git_diff", "diff", {"exit_code": proc.returncode})
            
            return {
                "success": True,
                "diff": stdout.decode()
            }
        except Exception as e:
            logger.error(f"Failed to get git diff: {e}")
            await self._publish_tool_event("git_diff", "error", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    async def run_tests(
        self,
        workspace_id: str,
        test_command: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run tests in the workspace"""
        try:
            if test_command is None:
                # Auto-detect test command based on repository
                test_command = await self._detect_test_command()
            
            proc = await asyncio.create_subprocess_exec(
                *test_command,
                cwd=self.workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            await self._publish_tool_event("run_tests", "run", {"command": test_command, "exit_code": proc.returncode})
            
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "output": stdout.decode(),
                "error": stderr.decode(),
            }
        except Exception as e:
            logger.error(f"Failed to run tests: {e}")
            await self._publish_tool_event("run_tests", "error", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _detect_test_command(self) -> List[str]:
        """Auto-detect appropriate test command"""
        # Check for common test files
        if os.path.exists(os.path.join(self.workspace_path, "go.mod")):
            return ["go", "test", "./..."]
        elif os.path.exists(os.path.join(self.workspace_path, "package.json")):
            return ["npm", "test"]
        elif os.path.exists(os.path.join(self.workspace_path, "Makefile")):
            return ["make", "test"]
        else:
            return ["echo", "No test command detected"]
    
    async def list_files(
        self,
        workspace_id: str,
        directory: str = ".",
    ) -> Dict[str, Any]:
        """List files in a directory"""
        try:
            full_path = os.path.join(self.workspace_path, directory.lstrip("/"))
            
            if not os.path.exists(full_path):
                return {
                    "success": False,
                    "directory": directory,
                    "error": f"Directory does not exist: {directory}"
                }
            
            files = []
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                files.append({
                    "name": item,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "path": os.path.join(directory, item).replace("\\", "/")
                })
            
            await self._publish_tool_event("list_files", "list", {"directory": directory, "count": len(files)})
            
            return {
                "success": True,
                "directory": directory,
                "files": files
            }
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            await self._publish_tool_event("list_files", "error", {"directory": directory, "error": str(e)})
            return {
                "success": False,
                "directory": directory,
                "error": str(e)
            }
    
    async def run_command(
        self,
        workspace_id: str,
        command: str,
        args: List[str] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Run a shell command in the workspace"""
        try:
            full_command = [command]
            if args:
                full_command.extend(args)
            
            proc = await asyncio.create_subprocess_exec(
                *full_command,
                cwd=self.workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {
                    "success": False,
                    "command": " ".join(full_command),
                    "error": f"Command timed out after {timeout} seconds"
                }
            
            await self._publish_tool_event("run_command", "execute", {
                "command": " ".join(full_command),
                "exit_code": proc.returncode
            })
            
            return {
                "success": proc.returncode == 0,
                "command": " ".join(full_command),
                "exit_code": proc.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
            }
        except Exception as e:
            logger.error(f"Failed to run command: {e}")
            await self._publish_tool_event("run_command", "error", {"command": command, "error": str(e)})
            return {
                "success": False,
                "command": command,
                "error": str(e)
            }
