import tiktoken

encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(messages):
  total = 0
  
  for msg in messages:
    total += len(encoding.encode(msg["content"]))
    
  return total
