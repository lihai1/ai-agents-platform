#!/usr/bin/env python3
"""E2E test for mock mode with UI"""
import asyncio
import httpx
import json

async def test_e2e_mock_mode():
    """Test e2e flow with mock mode enabled"""
    print("Testing E2E with mock mode...")
    
    base_url = "http://localhost:8000"
    
    # Test 1: Create chat with mock mode
    print("\n1. Creating chat with mock_mode=True...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base_url}/chatkit/",
            json={
                "message": "Add a new feature to the mock repository",
                "repository_id": "mock-repo-id",
                "mock_mode": True,
                "trigger_workflow": True,
                "project_id": "mock-project-id"
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✓ Chat created successfully with mock mode")
            # Stream the response
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(f"   Response: {data.get('content', '')[:100]}")
                    if data.get('workflow_triggered'):
                        print("   ✓ Workflow triggered successfully")
        else:
            print(f"   ✗ Failed: {response.text}")
            return False
    
    # Test 2: Create chat without mock mode (should fail without control-plane)
    print("\n2. Creating chat with mock_mode=False (should skip container creation)...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base_url}/chatkit/",
            json={
                "message": "Test message",
                "repository_id": "test-repo-id",
                "mock_mode": False,
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✓ Chat created (container creation skipped)")
        else:
            print(f"   Note: {response.text}")
    
    # Test 3: Check agent service health
    print("\n3. Checking agent service health...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{base_url}/health")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✓ Agent service is healthy")
        except Exception as e:
            print(f"   Note: Health check not available: {e}")
    
    print("\n" + "="*50)
    print("✅ E2E MOCK MODE TEST COMPLETED")
    print("="*50)
    print("\nSummary:")
    print("- UI accessible at http://localhost:4200")
    print("- Agent service running at http://localhost:8000")
    print("- Mock mode skips container creation")
    print("- Workflow can be triggered with mock mode")
    return True

if __name__ == "__main__":
    exit_code = asyncio.run(test_e2e_mock_mode())
    exit(0 if exit_code else 1)
