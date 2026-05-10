import httpx
import asyncio

async def test_ollama():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "http://127.0.0.1:11434/v1/chat/completions",
                json={
                    "model": "llama3.2:latest",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 10
                }
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama())
