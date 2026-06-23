# 使用 Dify 创建一个“相关技术简报邮件生成助手”

输入想要了解的技术关键词，就能得到一封包含技术讲解和最新新闻要点的简报邮件。

## 1. 用户输入节点

输入参数：

- `topic`: String - 内容主题

- `time_range`: Select - 选择资料和新闻的时间范围

- `max_news`: Number - 最大新闻数量

- `email`: String - 邮件的收件邮箱

## 2. Tavily 搜索节点

输出结果：

```json
{
  "text": "...markdown形式的全部内容...",
  "files": "...文件...",
  "json": [
    {
      "query": "...搜索提示词...",
      "request_id": "...请求ID...",
      "response_time": "...响应时间...",
      "results": [
        {
          "content": "...内容...",
          "score": "...相关度评分...",
          "title": "...题目...",
          "url": "..."
        },
        ...
      ]
    }
  ]
}
```

`content` 并不是完整的文章内容，较长的文章只截取了很小一部分开头文字。

> **TODO**: App 需要 “技术讲解 + 新闻要点”，一次搜索很难兼顾，可以拆分成两次搜索。

## 3. 代码节点 - 处理搜索得到的内容

对搜索得到的内容进行去重、排序与取 Top K 操作。

输出：

- `urls`: 逗号分隔的 URL 字符串。
- `articles`: 含 title, url, score, snippet 的原始内容。
- `url_count`: 总数量。

## 4. Tavily Extract 节点

访问 `urls` 中的所有 url，并提取与主题有关的特定数量片段，可用于 LLM 的提示词中。
