import requests
import os
from dotenv import load_dotenv

load_dotenv()


url = "https://api.deepseek.com/chat/completions"

headers = {
  "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
  "Content-Type": "application/json",
}

payload = {
  "model": "deepseek-chat",
  "messages": [
    {"role": "user", "content": "你好"}
  ]
}

res = requests.post(url=url, headers=headers, json=payload, timeout=10)

# 检查状态码
res.raise_for_status()

data = res.json() # 解析接受到的数据
print(data['choices'][0]['message']['content'])

