
import httpx
import asyncio

async def main():
    session_id = "2161476a-8025-4610-9724-77c31d305d2c"
    url = f"http://localhost:8000/sessions/{session_id}"
    print(f"Deleting {url}...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
