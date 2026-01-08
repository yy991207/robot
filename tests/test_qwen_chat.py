"""
测试通义千问 API 对话
"""

import asyncio
import httpx
import json


async def test_qwen_chat():
    """测试基本对话"""
    api_key = "sk-56c7427bd02243b5808da837d80ef6af"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    messages = [
        {"role": "system", "content": "你是一个友好的助手。"},
        {"role": "user", "content": "你是谁？"}
    ]
    
    payload = {
        "model": "qwen-plus",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("发送请求...")
    print(f"URL: {base_url}/chat/completions")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers
        )
        
        print(f"\n状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"\n回复: {content}")


async def test_qwen_stream():
    """测试流式对话"""
    api_key = "sk-56c7427bd02243b5808da837d80ef6af"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    messages = [
        {"role": "system", "content": "你是一个友好的助手。"},
        {"role": "user", "content": "你好，请简单介绍一下你自己。"}
    ]
    
    payload = {
        "model": "qwen-plus",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500,
        "stream": True
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("\n测试流式输出...")
    print("回复: ", end="", flush=True)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        continue
    
    print()


if __name__ == "__main__":
    print("=" * 50)
    print("测试通义千问 API")
    print("=" * 50)
    
    asyncio.run(test_qwen_chat())
    asyncio.run(test_qwen_stream())
