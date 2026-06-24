# “相关技术简报邮件生成助手”

节点级别的 App 流程解释。

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

> **TODO**: App 需要 “技术讲解 + 新闻要点”，一次搜索很难兼顾，可以拆分成两次搜索。√

## 3. 信息处理 Code 节点

对搜索得到的内容进行去重、排序与取 Top K 操作。

输出：

- `urls`: 逗号分隔的 URL 字符串。
- `articles`: 含 title, url, score, snippet 的原始内容。
- `url_count`: 总数量。

## 4. Tavily Extract 节点

访问 `urls` 中的所有 url，并提取与主题有关的特定数量片段，可用于 LLM 的提示词中。

输出有 `json` 和 `text` 类型。

## 5. 内容拼装 Code 节点

通过代码将 Extract 节点得到的具体文章片段和其他必要信息拼装成可直接发送给 LLM 的内容。

输出：

- `email_content`: 主要内容。

- `article_count`: 文章数量，供调试等情况使用。

## 6. LLM 节点 - 生成文章主体内容

提示词：

```txt
你是技术简报撰写助手。根据 {{#1782229945025.email_context#}} 中的资料写一封邮件，包含：

1. 【本周新闻要点】基于每条的 title、搜索摘要、URL，每条 2~3 句
2. 【技术讲解】基于深读片段，通俗解释主题，不编造片段中没有的内容
3. 语气专业简洁，800~1200 字，Markdown 格式
4. 只生成邮件主体内容，邮件头的问好和结尾都不要
```

> TODO: 输出的 text 中还包含了模型的完整思考过程，需要去除 √

增加了代码节点完成上述 TODO。

## 7. 内容处理拼装模块

1. `code`节点：从生成的邮件主体中去除模型的思考过程。

2. `template`节点：排版邮件正文形式。

3. `code` 节点：将 markdown 形式的邮件正文转换成 html。

4. `code`节点：构建 Resend 可接受的邮件正文内容。

## 8. HTTP 节点 - 发送邮件

使用 Resend 来发送邮件。

配置请求头：

- `Authorization`: `Bearer {{API_KEY}}`

- `Content_Type`: `application/json`

## OUTPUT 节点

输出结果。
