#!/usr/bin/env python3
"""Test script for AI Team streaming endpoint"""
import asyncio
import json
import httpx

async def test_chat_streaming():
    """Test the chat streaming endpoint"""
    url = "http://localhost:8000/api/llm/chat"
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": "Merhaba, basit bir Python fonksiyonu yaz: İki sayıyı toplayan bir fonksiyon"
            }
        ],
        "stream": True
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                print(await response.aread())
                return
            
            print("Streaming response:")
            print("-" * 60)
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        print("\n[DONE]")
                        break
                    try:
                        json_data = json.loads(data)
                        if "choices" in json_data and len(json_data["choices"]) > 0:
                            content = json_data["choices"][0].get("delta", {}).get("content", "")
                            if content:
                                print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        continue
                elif line.strip():
                    print(line)

if __name__ == "__main__":
    asyncio.run(test_chat_streaming())
