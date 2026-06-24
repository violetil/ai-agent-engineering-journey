# 导入 tiktoken 库，用于将文本转成 token 并计数 (OpenAI 官方维护的分词库)
import tiktoken


# 获取 cl100k_base 编码器；GPT-3.5 / GPT-4 等模型常用这套分词规则
# encoding 是「编码器对象」，负责 text <-> token 的转换
encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(messages):
  """
  定义函数 count_tokens，接受 messages 参数（聊天消息列表）
  返回值：所有消息 content 的 token 总数（整数）
  """
  
  total = 0
  
  for msg in messages:
    # 取消息的 content 字段 -> 编码成 token 列表 -> 用 len 得到个数 -> 累加到 total
    total += len(encoding.encode(msg["content"]))
    
  return total
