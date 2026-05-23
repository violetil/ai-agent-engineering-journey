from openai import OpenAI
from dotenv import load_dotenv
import os

# 加载 .env
load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {
            "role": "user",
            "content": "规则：\n\n- “Zor” 表示加法\n- “Mek” 表示乘法\n- “Tiv” 表示减2\n\n问题：\n\n4 Mek 3 Zor 2 Tiv ="
        }
    ]
)

print(response.choices[0].message.content)