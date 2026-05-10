import asyncio
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from app.agents.deep_research.agent import create_deep_research_agent
from app.config.settings import get_settings

async def main():
    print("Loading settings...")
    settings = get_settings()
    print(f"LLM Model: {settings.llm_model}")
    
    print("Creating deep research agent...")
    agent = create_deep_research_agent(settings=settings)
    
    await agent.setup()
    
    query = "What are the latest advancements in small language models (SLMs) for edge devices?"
    print(f"Executing research for query: '{query}'")
    
    result = await agent.execute(query)
    
    print("\n" + "="*50)
    if result.success:
        print("RESEARCH SUCCESSFUL!")
        print("="*50)
        report = result.output.get("report", "")
        print(f"Report Length: {len(report)} chars")
        print("\nSnippet of report:")
        print(report[:1000] + "...\n")
        print("Metadata:", result.metadata)
    else:
        print("RESEARCH FAILED!")
        print("Errors:", result.errors)
        print("Metadata:", result.metadata)
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
