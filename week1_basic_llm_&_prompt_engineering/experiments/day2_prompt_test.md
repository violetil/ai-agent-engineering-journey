# DAY 2: 不同 Prompt 对比

本实验测试不同角色 (system role) 和不同提示词技术 (zero-shot, few-shot) 对模型回答的影响

## 实验配置

- **模型**: `deepseek chat`
- **问题**: <写一个关于关于独角兽的一句睡前故事> <情感分类问题>

## 实验内容和结果

🔬 **实验组: question = 写一个关于关于独角兽的一句睡前故事 | system prompt = 你是一个专业助手**

模型回答：
小独角兽用它的角尖轻轻触碰夜空的星星，每一颗被点亮的星星都变成了甜甜的梦，悄悄地落进每一个孩子的枕头里。

---

🔬 **实验组: question = 写一个关于关于独角兽的一句睡前故事 | system prompt = 你是一个海盗**

模型回答：
在银色的月光下，一只独角兽把彩虹打成了结，系在海浪的尾巴上，梦里的小船就能顺着那道光弧，滑到银河的尽头去捞星星。

---

🔬 **实验组: question = 情感分类问题 | prompt tech = zero_shot**

提示词：

```
Classify the text into neutral, negative or positive.
Text: I think the vacation is okay
Sentiment:
```

模型回答：
neutral

---

🔬 **实验组: question = 情感分类问题 | prompt tech = few_shot**

提示词：

```
Classify the text into neutral, negative or positive.
Text: The restaurant had excellent service and the food arrived quickly
Sentiment: positive
Text: The headphones have terrible sound quality and are uncomfortable to wear
Sentiment: negative
Text: I think the vacation is okay
Sentiment:
```

模型回答：
neutral

---

## 实验总结

通过设定不同的系统角色，能够让模型的语气有非常大的不同。

而 zero-shot 和 few-shot 在此次实验中没有任何区别。因为现在强模型本身就会 CoT，所以普通的分类，算数问题已经看不出这类简单样例带来的回答提升。

所以现代工业上更偏向使用以下方式测试：

- 长链推理
- 隐含规则学习
- 输出格式控制
- 风格学习
