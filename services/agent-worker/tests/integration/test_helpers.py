"""Test helpers for agent-worker integration tests"""
import asyncio
import uuid
import os
import json
from typing import Optional, Dict, Any, List


class WorkerTestHelper:
    """Helper class for agent-worker integration tests"""
    
    def __init__(self, nats_client):
        self.nc = nats_client
        self.collected_events: Dict[str, List[Dict]] = {}
        self.subscriptions = []
    
    async def subscribe_to_worker_events(
        self, 
        user_id: str, 
        run_id: str, 
        timeout: float = 5.0
    ) -> None:
        """Subscribe to worker state events with timeout"""
        subject = f"agent.user.{user_id}.events.{run_id}.state.>"
        self.collected_events[f"state_{run_id}"] = []
        
        async def event_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                self.collected_events[f"state_{run_id}"].append({
                    "subject": msg.subject,
                    "data": data,
                })
            except Exception as e:
                print(f"Error processing event: {e}")
        
        # Use raw NATS client for callback-based subscription
        sub = await self.nc.nc.subscribe(subject, cb=event_handler)
        self.subscriptions.append(sub)
    
    async def subscribe_to_worker_chat_events(
        self, 
        user_id: str, 
        run_id: str, 
        timeout: float = 5.0
    ) -> None:
        """Subscribe to worker chat events with timeout"""
        subject = f"agent.user.{user_id}.chat.{run_id}.events"
        self.collected_events[f"chat_{run_id}"] = []
        
        async def chat_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                self.collected_events[f"chat_{run_id}"].append({
                    "subject": msg.subject,
                    "data": data,
                })
            except Exception as e:
                print(f"Error processing chat event: {e}")
        
        # Use raw NATS client for callback-based subscription
        sub = await self.nc.nc.subscribe(subject, cb=chat_handler)
        self.subscriptions.append(sub)
    
    async def wait_for_event(
        self, 
        run_id: str, 
        event_type: str, 
        timeout: float = 5.0
    ) -> Optional[Dict]:
        """Wait for a specific event type with timeout"""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if f"state_{run_id}" in self.collected_events:
                for event in self.collected_events[f"state_{run_id}"]:
                    if event["data"].get("event_type") == event_type:
                        return event
            await asyncio.sleep(0.1)
        
        return None
    
    async def wait_for_chat_event(
        self, 
        run_id: str, 
        event_type: str, 
        timeout: float = 5.0
    ) -> Optional[Dict]:
        """Wait for a specific chat event type with timeout"""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if f"chat_{run_id}" in self.collected_events:
                for event in self.collected_events[f"chat_{run_id}"]:
                    if event["data"].get("event_type") == event_type:
                        return event
            await asyncio.sleep(0.1)
        
        return None
    
    def get_state_events(self, run_id: str) -> List[Dict]:
        """Get all collected state events for a run"""
        return self.collected_events.get(f"state_{run_id}", [])
    
    def get_chat_events(self, run_id: str) -> List[Dict]:
        """Get all collected chat events for a run"""
        return self.collected_events.get(f"chat_{run_id}", [])
    
    async def cleanup(self) -> None:
        """Clean up subscriptions"""
        for sub in self.subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                print(f"Error unsubscribing: {e}")
        self.subscriptions.clear()


def setup_worker_env(run_id: str, user_id: str = "test-user-123") -> None:
    """Set up environment variables for worker tests"""
    os.environ["USER_ID"] = user_id
    os.environ["TASK"] = "Test task"
    os.environ["PROJECT_ID"] = "test-project"
    os.environ["REPOSITORY_ID"] = "test-repo"
    os.environ["MAX_TOKENS"] = "1000"
    os.environ["MAX_COST"] = "0.1"
    os.environ["MAX_REPAIR_COUNT"] = "2"
    os.environ["AGENT_TYPE"] = "specialist"
    os.environ["LLM_PROVIDER"] = "fake"
    os.environ["MODEL_NAME"] = "test-model"


def create_user_event(
    run_id: str, 
    user_id: str, 
    event_type: str = "approval", 
    approved: bool = True
) -> Dict[str, Any]:
    """Create a user event message for testing"""
    return {
        "message_id": str(uuid.uuid4()),
        "event_type": event_type,
        "run_id": run_id,
        "payload": {
            "approval_id": f"approval-{uuid.uuid4().hex[:8]}",
            "approved": approved,
        },
        "timestamp": "2026-07-10T10:19:53.178810",
        "schema_version": "1.0",
    }
