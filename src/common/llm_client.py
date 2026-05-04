import sys
sys.path.insert(0, '/Users/elwood/Desktop/test/AegisLink')

import requests
import json

API_SECRET_KEY = "***"
BASE_URL = "https://api.***.cn/v1/chat/completions"

def chat(user_prompt, system_prompt=None, history=None):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    payload = json.dumps({
        "model": "deepseek-v3.2",
        "messages": messages,
        "stream": False,
        "max_tokens": 2048,
        "top_k": 0,
        "repetition_penalty": 1.05,
        "num_beams": 1,
        "user": "andy",
        "content_filter": False
    })

    headers = {
        'Authorization': API_SECRET_KEY,
        'Content-Type': 'application/json'
    }

    response = requests.post(BASE_URL, headers=headers, data=payload)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"API 调用失败，状态码: {response.status_code}, 信息: {response.text}")
