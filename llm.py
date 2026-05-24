from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
  api_key=os.getenv("DEEPSEEK_API_KEY"),
  base_url="https://api.deepseek.com"
)

def ask_llm(sys_prompt, user_prompt, temperature=0, output_type="text"):
  response = client.chat.completions.create(
    model="deepseek-chat",
    temperature=temperature,
    response_format={
      "type": output_type
    },
    messages=[
      {
        "role": "system",
        "content": sys_prompt
      },
      {
        "role": "user",
        "content": user_prompt
      }
    ]
  )
  
  return response.choices[0].message.content