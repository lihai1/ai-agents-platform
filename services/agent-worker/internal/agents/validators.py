"""Validation agents for testing, review, and verification"""
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_agent
from langchain_core.tools import tool
from internal.agents.schemas import TestResult, ReviewResult, ReviewFinding, VerificationResult, CriterionResult
from internal.agents.model_factory import get_model
from internal.tools.workspace import WorkspaceTools
import json
import logging
import re

logger = logging.getLogger(__name__)


def _parse_test_output(test_output: str) -> dict:
    """Parse test output from go test or simple summaries."""
    total = passed = failed = skipped = 0
    try:
        # Look for explicit counts first (e.g. "1 passed, 0 failed")
        passed_match = re.search(r"(\d+)\s+passed", test_output, re.IGNORECASE)
        failed_match = re.search(r"(\d+)\s+failed", test_output, re.IGNORECASE)
        skipped_match = re.search(r"(\d+)\s+skipped", test_output, re.IGNORECASE)
        if passed_match or failed_match:
            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            skipped = int(skipped_match.group(1)) if skipped_match else 0
        else:
            # Fallback for go test output: "ok" or "PASS" means all passed,
            # "FAIL" or "--- FAIL" means at least one failed.
            if re.search(r"FAIL|---\s*FAIL", test_output, re.IGNORECASE):
                failed = 1
            elif re.search(r"ok\s|PASS", test_output, re.IGNORECASE):
                passed = 1
        total = passed + failed + skipped
    except Exception as e:
        logger.warning(f"Failed to parse test output: {e}")
    return {
        "total_tests": total or 1,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


def _parse_test_result(result: dict) -> TestResult:
    """Parse an AgentExecutor result into a TestResult"""
    output_text = result.get("output", "")
    test_output = ""
    success = False
    intermediate_steps = result.get("intermediate_steps", [])
    for action, observation in intermediate_steps:
        try:
            tool_name = getattr(action, "tool", None)
            if tool_name == "run_tests":
                obs = json.loads(observation) if isinstance(observation, str) else observation
                if obs.get("success"):
                    success = True
                    test_output = obs.get("output", "")
                else:
                    test_output = obs.get("error", "") or obs.get("output", "")
        except Exception as e:
            logger.warning(f"Failed to parse test step: {e}")

    if not test_output and output_text:
        test_output = output_text

    metrics = _parse_test_output(test_output)
    return TestResult(
        total_tests=metrics["total_tests"],
        passed=metrics["passed"],
        failed=metrics["failed"],
        skipped=metrics["skipped"],
        coverage=0.0,
        test_output=test_output,
        failed_tests=[]
    )


def _parse_review_result(result: dict) -> ReviewResult:
    """Parse an AgentExecutor result into a ReviewResult"""
    output = result.get("output", "")
    decision = "approved" if "approved" in output.lower() else "changes_required"
    return ReviewResult(
        decision=decision,
        findings=[],
        summary=output or "Code review completed"
    )


def _parse_verification_result(
    result: dict,
    implementation_plan: Dict[str, Any],
    test_results: Any,
    review_results: Any,
) -> VerificationResult:
    """Parse an AgentExecutor result into a VerificationResult"""
    output = result.get("output", "")
    criteria = implementation_plan.get("acceptance_criteria", []) if implementation_plan else []
    test_passed = bool(test_results and getattr(test_results, "passed", test_results.get("passed", 0)) > 0)
    review_decision = review_results.decision if hasattr(review_results, "decision") else review_results.get("decision", "approved")
    accepted = test_passed and review_decision != "rejected"

    criteria_results = [
        CriterionResult(
            criterion=c,
            passed=accepted,
            evidence=output or "Verified through testing and code review"
        )
        for c in criteria
    ] if criteria else [
        CriterionResult(
            criterion="Implementation",
            passed=accepted,
            evidence=output or "Verified through testing and code review"
        )
    ]

    return VerificationResult(
        accepted=accepted,
        criteria_results=criteria_results,
        summary=output or "Verification completed"
    )


class BackendTestEngineerAgent:
    """Agent for backend testing (Go, Python, etc.)"""

    def __init__(self, model_name: str = "gpt-4", mock_mode: bool = False, llm_provider: str = None):
        self.model = get_model(model_name=model_name, mock_mode=mock_mode, llm_provider=llm_provider)
        self.mock_mode = mock_mode
        self.llm_provider = llm_provider
    
    async def run_tests(
        self,
        task: str,
        implementation_plan: Dict[str, Any],
        workspace_id: str,
        workspace_tools: WorkspaceTools,
        run_id: Optional[str] = None,
    ) -> TestResult:
        """Run backend tests"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a backend test engineer agent. Your job is to execute and analyze test results.

Analyze the test output and provide:
- Total number of tests run
- Number of tests passed
- Number of tests failed
- Number of tests skipped
- Code coverage percentage if available
- Full test output
- List of failed test names"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Run the tests and analyze the results.""")
        ])
        
        # Create tools
        @tool
        async def run_tests(test_command: Optional[str] = None) -> str:
            """Run tests in the workspace"""
            cmd = test_command.split() if test_command else None
            result = await workspace_tools.run_tests(workspace_id, cmd)
            return json.dumps(result)
        
        @tool
        async def read_file(file_path: str) -> str:
            """Read a file from the workspace"""
            result = await workspace_tools.read_file(workspace_id, file_path)
            return json.dumps(result)
        
        tools = [run_tests, read_file]
        
        # Create agent
        agent = create_agent(self.model, tools, system_prompt=prompt)
        # LangChain 0.3+ pattern - invoke agent directly
        try:
            result = await agent.ainvoke({
                "task": task,
                "implementation_plan": json.dumps(implementation_plan, indent=2),
            })
            
            return _parse_test_result(result)
            
        except Exception as e:
            logger.error(f"Backend test engineer agent failed: {e}")
            return TestResult(
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                coverage=0.0,
                test_output=str(e),
                failed_tests=[]
            )


class AngularTestEngineerAgent:
    """Agent for Angular testing"""

    def __init__(self, model_name: str = "gpt-4", mock_mode: bool = False, llm_provider: str = None):
        self.model = get_model(model_name=model_name, mock_mode=mock_mode, llm_provider=llm_provider)
        self.mock_mode = mock_mode
        self.llm_provider = llm_provider
    
    async def run_tests(
        self,
        task: str,
        implementation_plan: Dict[str, Any],
        workspace_id: str,
        workspace_tools: WorkspaceTools,
        run_id: Optional[str] = None,
    ) -> TestResult:
        """Run Angular tests"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an Angular test engineer agent. Your job is to execute and analyze Angular test results.

Analyze the test output and provide:
- Total number of tests run
- Number of tests passed
- Number of tests failed
- Number of tests skipped
- Code coverage percentage if available
- Full test output
- List of failed test names"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Run the Angular tests and analyze the results.""")
        ])
        
        # Create tools
        @tool
        async def run_tests(test_command: Optional[str] = None) -> str:
            """Run tests in the workspace"""
            cmd = test_command.split() if test_command else None
            result = await workspace_tools.run_tests(workspace_id, cmd)
            return json.dumps(result)
        
        @tool
        async def read_file(file_path: str) -> str:
            """Read a file from the workspace"""
            result = await workspace_tools.read_file(workspace_id, file_path)
            return json.dumps(result)
        
        tools = [run_tests, read_file]
        
        # Create agent
        agent = create_agent(self.model, tools, system_prompt=prompt)
        # LangChain 0.3+ pattern - invoke agent directly
        try:
            result = await agent.ainvoke({
                "task": task,
                "implementation_plan": json.dumps(implementation_plan, indent=2),
            })
            
            return _parse_test_result(result)
            
        except Exception as e:
            logger.error(f"Angular test engineer agent failed: {e}")
            return TestResult(
                total_tests=0,
                passed=0,
                failed=0,
                skipped=0,
                coverage=0.0,
                test_output=str(e),
                failed_tests=[]
            )


class CodeReviewerAgent:
    """Agent for code review"""

    def __init__(self, model_name: str = "gpt-4", mock_mode: bool = False, llm_provider: str = None):
        self.model = get_model(model_name=model_name, mock_mode=mock_mode, llm_provider=llm_provider)
        self.mock_mode = mock_mode
        self.llm_provider = llm_provider
    
    async def review(
        self,
        task: str,
        implementation_plan: Dict[str, Any],
        code_diff: str,
        workspace_id: str,
        workspace_tools: WorkspaceTools,
        run_id: Optional[str] = None,
    ) -> ReviewResult:
        """Review code changes"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a code reviewer agent. Your job is to review code changes for correctness, maintainability, security, and best practices.

Provide review findings with severity levels:
- blocking: Must be fixed before merge
- high: Should be fixed
- medium: Nice to have
- low: Minor suggestions

Your review should cover:
- Correctness and logic
- Security vulnerabilities
- Performance issues
- Code style and readability
- Error handling
- Test coverage
- Documentation"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Code Diff:
{code_diff}

Review the changes and provide findings.""")
        ])
        
        # Create tools
        @tool
        async def read_file(file_path: str) -> str:
            """Read a file from the workspace"""
            result = await workspace_tools.read_file(workspace_id, file_path)
            return json.dumps(result)
        
        @tool
        async def git_diff() -> str:
            """Get git diff"""
            result = await workspace_tools.git_diff(workspace_id)
            return json.dumps(result)
        
        tools = [read_file, git_diff]
        
        # Create agent
        agent = create_agent(self.model, tools, system_prompt=prompt)
        # LangChain 0.3+ pattern - invoke agent directly
        try:
            result = await agent.ainvoke({
                "task": task,
                "implementation_plan": json.dumps(implementation_plan, indent=2),
                "code_diff": code_diff,
            })
            
            return _parse_review_result(result)
            
        except Exception as e:
            logger.error(f"Code reviewer agent failed: {e}")
            return ReviewResult(
                decision="rejected",
                findings=[
                    ReviewFinding(
                        severity="blocking",
                        message=f"Review failed: {str(e)}",
                        file=None,
                        line=None
                    )
                ],
                summary="Review failed due to error"
            )


class CompletionVerifierAgent:
    """Agent for verifying completion against acceptance criteria"""

    def __init__(self, model_name: str = "gpt-4", mock_mode: bool = False, llm_provider: str = None):
        self.model = get_model(model_name=model_name, mock_mode=mock_mode, llm_provider=llm_provider)
        self.mock_mode = mock_mode
        self.llm_provider = llm_provider
    
    async def verify(
        self,
        task: str,
        implementation_plan: Dict[str, Any],
        test_results: TestResult,
        review_results: ReviewResult,
        workspace_id: str,
        workspace_tools: WorkspaceTools,
        run_id: Optional[str] = None,
    ) -> VerificationResult:
        """Verify completion against acceptance criteria"""
        
        # Initialize WorkspaceTools with run_id for event publishing
        if run_id and not workspace_tools.run_id:
            workspace_tools.run_id = run_id
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a completion verifier agent. Your job is to verify that the implementation meets all acceptance criteria.

For each acceptance criterion:
- Determine if it was met (passed/failed)
- Provide evidence for your decision

Your final decision should be:
- accepted: All criteria are met
- rejected: One or more criteria are not met"""),
            ("human", """Task: {task}

Implementation Plan:
{implementation_plan}

Acceptance Criteria:
{acceptance_criteria}

Test Results:
{test_results}

Review Results:
{review_results}

Verify completion against the acceptance criteria.""")
        ])
        
        # Create tools
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
        
        tools = [read_file, git_status, git_diff]
        
        # Create agent
        agent = create_agent(self.model, tools, system_prompt=prompt)
        # LangChain 0.3+ pattern - invoke agent directly
        try:
            result = await agent.ainvoke({
                "task": task,
                "implementation_plan": json.dumps(implementation_plan, indent=2),
                "acceptance_criteria": json.dumps(implementation_plan.get("acceptance_criteria", []), indent=2),
                "test_results": test_results.model_dump_json(indent=2),
                "review_results": review_results.model_dump_json(indent=2),
            })
            
            return _parse_verification_result(result, implementation_plan, test_results, review_results)
            
        except Exception as e:
            logger.error(f"Completion verifier agent failed: {e}")
            return VerificationResult(
                accepted=False,
                criteria_results=[
                    CriterionResult(
                        criterion="Verification",
                        passed=False,
                        evidence=f"Verification failed: {str(e)}"
                    )
                ],
                summary="Verification failed due to error"
            )
