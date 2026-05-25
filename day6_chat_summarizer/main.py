from summarizer import summarize_chat

messages = [
  {
      "role": "user",
      "content": "你好"
  },
  {
      "role": "assistant",
      "content": "你好，我是你的AI助手"
  },
  {
      "role": "user",
      "content": "我最近在学习 asyncio"
  },
  {
      "role": "assistant",
      "content": "asyncio 对 Agent 很重要"
  },
  {
      "role": "user",
      "content": "我还想学习 LangGraph"
  }
]

summary = summarize_chat(messages)

print(summary)