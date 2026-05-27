from token_manager import count_tokens

messages = [
  { "role": "user", "content": "hello" },
  { "role": "assitant", "content": "hi" } 
]

if count_tokens(messages) == 2:
  print("测试通过")
else:
  print("测试失败")