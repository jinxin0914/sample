import requests

def call_api():
    url = "http://localhost:8080/api/version"
    try:
        response = requests.get(url, timeout=5)  # 设置5秒超时
        response.raise_for_status()  # 如果HTTP返回状态码不是200，抛出异常
        print(f"API调用成功！响应内容: {response.text}")
        return response.json()  # 如果返回的是JSON数据
    except requests.exceptions.RequestException as e:
        print(f"API调用失败: {e}")
        return None

if __name__ == "__main__":
    call_api()

import requests
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def call_api_with_retry(url, max_retries=3, retry_delay=2):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            logger.info(f"API调用成功 (尝试 {attempt + 1}/{max_retries}): {response.text}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)  # 延迟后重试
    logger.error("所有重试均失败！")
    return None

if __name__ == "__main__":
    call_api_with_retry("http://localhost:8080/api/version")



import requests

def call_api_with_auth():
    url = "http://localhost:8080/api/version"
    token = "your_jwt_token_here"  # 替换为实际Token
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        print(f"响应: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    call_api_with_auth()


import aiohttp
import asyncio

async def call_api_async():
    url = "http://localhost:8080/api/version"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=5) as response:
                response.raise_for_status()
                data = await response.json()
                print(f"异步API调用成功: {data}")
                return data
        except Exception as e:
            print(f"异步API调用失败: {e}")
            return None

if __name__ == "__main__":
    asyncio.run(call_api_async())
