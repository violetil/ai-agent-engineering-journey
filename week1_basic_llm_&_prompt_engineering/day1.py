from openai import OpenAI
from dotenv import load_dotenv
import os

# 加载 .env
load_dotenv()

# 创建 openai 客户端，指定 base_url 到 deepseek
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 设置模型参数
temperature = [0, 0.7, 1.5, 2]
top_p = [0.1, 0.5, 1]

# 打开文件，记录实验结果
with open("experiments/day1_effect_of_parameters_2.md", "w", encoding="utf-8") as f:
  # metadata
  f.write("# DAY 1: 参数影响总结\n\n本报告自动记录了不同 `temperature` 和 `top_p` 组合下模型的回答差异。\n\n## 实验配置\n\n- **模型**：`deepseek chat`\n- **问题**：如何让一家濒临倒闭的咖啡店在30天内重新盈利？\n\n## 实验内容和结果\n\n")
  
  # 嵌套循环：遍历每一种参数组合
  for temp in temperature:
    for p in top_p:
      print(f"实验：temperature={temp}, top_p={p} ...")
      
      # 发送请求
      response = client.chat.completions.create(
          model="deepseek-chat",
          temperature=temp,
          top_p=p,
          messages=[
              {
                  "role": "system",
                  "content": "回答控制在一段话"
              },
              {
                  "role": "user",
                  "content": "如何让一家濒临倒闭的咖啡店在30天内重新盈利？"
              }
          ]
      )
      
      ans = response.choices[0].message.content
      
      # 写入实验结果
      f.write(f"🔬 **实验组: temperature = {temp} | top_p = {p}**\n\n")
      f.write(f"模型回答：\n")
      f.write(f"{ans}\n\n")
      f.write(" \n---\n\n") # 加上分割线区分不同实验组
      
print("🎉 所有参数组合实验完毕！结果已汇总保存至 experiments/day1_effect_of_parameters_2.md")
