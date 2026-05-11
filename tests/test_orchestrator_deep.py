import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.orchestrator.agent import create_orchestrator_agent
from app.agents.orchestrator.config import OrchestratorConfig
from app.core.logging import configure_logging

async def main():
    configure_logging(level="INFO")
    
    config = OrchestratorConfig(
        max_iterations=1,
    )
    
    agent = create_orchestrator_agent(config=config)
    
    query = "Analyze the competitive landscape of decentralized AI infrastructure in 2026, focusing on Bittensor, Ritual, and Morpheus."
    
    print(f"\nStarting Orchestrator with Deep Research...")
    print(f"Query: '{query}'")
    print("="*60)
    
    # We pass a task that is likely to trigger deep research
    result = await agent.execute({
        "task": query,
        "send_email": False
    })
    
    if result.success:
        print("\n✅  ORCHESTRATOR SUCCESS")
        report = result.output.get("report", "")
        print(f"Report length: {len(report)} chars")
        
        # Check if deep research was used in the plan
        plan = result.output.get("plan", [])
        deep_used = any(s.get("step_type") == "deep_research" for s in plan)
        print(f"Deep Research triggered: {deep_used}")
        
        print("\n--- Report Snippet ---")
        print(report[:1000] + "...")
    else:
        print("\n❌  ORCHESTRATOR FAILED")
        print("Errors:", result.errors)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
