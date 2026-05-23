from openai import OpenAI
from dotenv import load_dotenv
import os

# 加载 .env
load_dotenv()

# 创建 openai 客户端
client = OpenAI(
  api_key=os.getenv("DEEPSEEK_API_KEY"),
  base_url="https://api.deepseek.com"
)

# 测试矩阵
promp_techs = ['zero_shot', 'few_shot']
sys_prompts = ['你是一个专业助手', '你是一个海盗']

with open("experiments/day2_prompt_test.md", "w", encoding="utf-8") as f:
  # metadata
  f.write("# DAY 2: 不同 Prompt 对比\n\n")
  f.write("本实验测试不同角色 (system role) 和不同提示词技术 (zero-shot, few-shot) 对模型回答的影响\n\n")
  f.write("## 实验配置\n\n")
  f.write("- **模型**: `deepseek chat`\n")
  f.write("- **问题**: <写一个关于关于独角兽的一句睡前故事> <Classify the text into neutral, negative or positive. Text: I think the vacation is okay>\n\n")
  f.write("## 实验内容和结果\n\n")
  
  # 系统角色测试
  for sys_prompt in sys_prompts:
    print(f"实验：question = 写一个关于关于独角兽的一句睡前故事 | system prompt = {sys_prompt} ...")
    
    response = client.chat.completions.create(
      model="deepseek-chat",
      messages=[
        {
          "role": "system",
          "content": sys_prompt
        },
        {
          "role": "user",
          "content": "写一个关于关于独角兽的一句睡前故事"
        }
      ]
    )
    
    ans = response.choices[0].message.content
    
    # 写入实验结果
    f.write(f"🔬 **实验组: question = 写一个关于关于独角兽的一句睡前故事 | system prompt = {sys_prompt}**\n\n")
    f.write(f"模型回答：\n")
    f.write(f"{ans}\n\n")
    f.write(" \n---\n\n") # 加上分割线区分不同实验组
  
  # 提示词技术测试
  for tech in promp_techs:
    print(f"实验：question = Text: I think the vacation is okay | prompt tech = {tech} ...")
    
    if tech == "zero_shot":
      content = "Classify the text into neutral, negative or positive.\n\nText: I think the vacation is okay\n\nSentiment:"
    else:
      content = "Classify the text into neutral, negative or positive.\n\nText: The restaurant had excellent service and the food arrived quickly\n\nSentiment: positive\n\nText: The headphones have terrible sound quality and are uncomfortable to wear\n\nSentiment: negative\n\nText: I think the vacation is okay\n\nSentiment:"
    
    response = client.chat.completions.create(
      model="deepseek-chat",
      messages=[
        {
          "role": "user",
          "content": content
        }
      ]
    )
    
    ans = response.choices[0].message.content
    
    # 写入实验结果
    f.write(f"🔬 **实验组: question = Text: I think the vacation is okay | prompt tech = {tech}**\n\n")
    f.write(f"模型回答：\n")
    f.write(f"{ans}\n\n")
    f.write(" \n---\n\n") # 加上分割线区分不同实验组
  
print("🎉 所有参数组合实验完毕！结果已汇总保存至 experiments/day2_prompt_test.md.md")
