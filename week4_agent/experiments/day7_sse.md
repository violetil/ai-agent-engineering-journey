# Day 7：把 agent 挂到 ai_service，用 SSE 推出每一步

`POST /agent/run` 复用 week3 的 JWT 和每日额度。请求体里的 `mode` 决定走纯循环还是计划模式。下面两段是同一次任务「北京和上海哪个更暖和」的原始输出，token 被换成了 `<...>`。

命令用的是 PowerShell 里的 `curl`，没有加 `curl.exe -N`。贴出来的是完整响应，帧和帧之间没有时间戳，所以这份记录证明了帧的内容和顺序，没有证明它们是逐条到达的。

## 终端输出

**纯循环**

```powershell
PS E:\Workbench\Personal\python\llm_lab> curl -X POST http://localhost:8000/agent/run `
>> -H "Content-Type: application/json" `
>> -H "Authorization: Bearer <...>" `
>> -d '{"task": "北京和上海哪个更暖和", "mode": "loop"}'
event: step
data: {"index": 1, "thought": "", "tool_name": "get_weather", "tool_args": "{\"city\": \"北京\"}", "tool_result": "晴天 25度", "prompt_tokens": 758, "completion_tokens": 67, "latency_ms": 2788}

event: step
data: {"index": 1, "thought": "", "tool_name": "get_weather", "tool_args": "{\"city\": \"上海\"}", "tool_result": "小雨 20度", "prompt_tokens": 758, "completion_tokens": 67, "latency_ms": 2788}

event: step
data: {"index": 2, "thought": "目前两地气温对比：\n\n- **北京**：晴天，25℃\n- **上海**：小雨，20℃\n\n所以**北京更暖和**，比上海高 5℃。\n\n不过要注意，这只是当下的气温。北京是晴天干燥，昼夜温差通常较大；上海湿度高，体感温度和气温差别会比较明显，20℃的雨天可能会觉得有点凉。", "tool_name": null, "tool_args": null, "tool_result": null, "prompt_tokens": 853, "completion_tokens": 77, "latency_ms": 1125}

event: done
data: {"answer": "目前两地气温对比：\n\n- **北京**：晴天，25℃\n- **上海**：小雨，20℃\n\n所以**北京更暖和**，比上海高 5℃。\n\n不过要注意，这只是当下的气温。北京是晴天干燥，昼夜温差通常较大；上海湿度高，体感温度和气温差别会比较明显，20℃的雨天可能会觉得有点凉。"}
```

**计划**

```powershell
PS E:\Workbench\Personal\python\llm_lab> curl -X POST http://localhost:8000/agent/run `
>> -H "Content-Type: application/json" `
>> -H "Authorization: Bearer <...>" `
>> -d '{"task": "北京和上海哪个更暖和", "mode": "plan"}'
event: plan
data: {"reasoning": "需要分别获取北京和上海的当前气温，再比较哪个更高。两个查询互相独立，可分别执行。", "steps": [{"id": 1, "goal": "获取北京当前的天气和气温", "depends_on": [], "suggested_tool": "get_weather"}, {"id": 2, "goal": "获取上海当前的天气和气温", "depends_on": [], "suggested_tool": "get_weather"}, {"id": 3, "goal": "比较两地的气温，判断哪个城市更暖和", "depends_on": [1, 2], "suggested_tool": null}]}

event: step
data: {"plan_step": 1, "index": 1, "thought": "", "tool_name": "get_weather", "tool_args": "{\"city\": \"北京\"}", "tool_result": "晴天 25度", "prompt_tokens": 843, "completion_tokens": 38, "latency_ms": 919}

event: step
data: {"plan_step": 1, "index": 2, "thought": "北京当前天气：晴，气温 25℃。", "tool_name": null, "tool_args": null, "tool_result": null, "prompt_tokens": 897, "completion_tokens": 11, "latency_ms": 753}

event: step_result
data: {"plan_step": 1, "status": "success", "output": "北京当前天气：晴，气温 25℃。", "note": null}

event: step
data: {"plan_step": 2, "index": 1, "thought": "", "tool_name": "get_weather", "tool_args": "{\"city\": \"上海\"}", "tool_result": "小雨 20度", "prompt_tokens": 843, "completion_tokens": 38, "latency_ms": 569}

event: step
data: {"plan_step": 2, "index": 2, "thought": "上海当前天气：小雨，气温 20 度。", "tool_name": null, "tool_args": null, "tool_result": null, "prompt_tokens": 897, "completion_tokens": 12, "latency_ms": 1028}

event: step_result
data: {"plan_step": 2, "status": "success", "output": "上海当前天气为小雨，气温20度。", "note": null}

event: step
data: {"plan_step": 3, "index": 1, "thought": "根据已知信息：北京 25℃，上海 20℃，北京比上海高 5℃，北京更暖和。", "tool_name": null, "tool_args": null, "tool_result": null, "prompt_tokens": 874, "completion_tokens": 23, "latency_ms": 922}

event: step_result
data: {"plan_step": 3, "status": "success", "output": "北京 25℃，上海 20℃，北京比上海高 5℃，北京更暖和。", "note": null}

event: done
data: {"answer": "根据当前天气数据，北京的气温是25℃，天气晴朗；上海的气温是20℃，有小雨。北京比上海高出5℃，因此北京更暖和。"}
```

## 从帧里能读出的事

纯循环只有 `step` 和 `done`。前两帧的 `index`、`prompt_tokens`（758）、`latency_ms`（2788）完全相同，工具分别是北京和上海。这是同一次模型调用返回了两个 `tool_calls`，不是循环转了两轮。第三帧 `index` 变成 2，`tool_name` 为 null，才是最终回答。按 index 去重后，循环本身是 758 + 853 = 1611 in，67 + 77 = 144 out。把三帧的 token 直接相加会把第一轮算两次。

`done` 的 `answer` 和最后一帧 `thought` 是同一段文字。纯循环没有再做一次总结调用。

计划模式的帧序是 `plan` → 每步的 `step` → `step_result` → `done`，没有 `replan`。计划是 3 步：两步查询互不依赖，对比步 `depends_on` 为 `[1, 2]`。

每个 `plan_step` 的 `index` 都从 1 重新计。步骤 1 和步骤 2 的第一轮输入都是 843，不是纯循环那种一轮比一轮大。这是每步一份新的 `messages`。步骤 3 没有工具调用，输入 874，它用的是黑板上两步的结论。

步骤 2 的 `thought` 是「上海当前天气：小雨，气温 20 度。」，紧接着的 `step_result.output` 是「上海当前天气为小雨，气温20度。」。`extract_result` 改写了措辞，事实还在。`done` 又和步骤 3 的 output 不同，那是 `summarize` 的另一次调用。这三处 token 都不在上面的 `step` 帧里。

## 验收结果

1. **额度在第一个字节之前拦截。** `DAILY_QUOTA_LIMIT=3`，当天额度用完后的下一次请求返回的是 HTTP 403，不是 200 空流：

```powershell
HTTP/1.1 403 Forbidden
date: Sat, 24 Oct 2026 13:33:17 GMT
server: uvicorn
content-length: 60
content-type: application/json

{"error":{"code":"QUOTA_EXCEEDED","message":"额度不够"}}
```

2. **扣费不依赖流结束。** 打出第一帧后 `Ctrl+C` 断开，再看 `data/users.json`，`daily_quota` 已经少了 1。修改前后的具体数字没有留在这份记录里。

3. **事件循环没有被这次 agent 堵住。** agent 还在跑的时候，另一个终端请求 `GET /` 立刻返回，没有等到 agent 结束。没有记耗时。

没有做的两项：帧是否逐条到达；运行期故障会不会变成 `event: error` 而不是把进程打崩。

## 结论

同一个任务，两种模式都给出「北京 25 度、上海 20 度、北京更暖」，和 `get_weather` 的假数据一致。SSE 把 week4 里原来打在终端上的计划和每一步，原样推到了 HTTP 客户端。

纯循环用一次模型调用查了两个城市。计划模式把这件事拆成三次独立的小循环，对比步没有再调工具。串行计划因此更贵，这和 day5 的对照一致；这次没有并行，也没有计墙上时间。

额度超限时，响应在任何 SSE 帧之前就以 403 JSON 结束。中途断开连接之后额度已经扣过。这两条对上了 week3 里「校验和扣费必须发生在第一个字节之前」的修法。

## 已知问题

客户端断开时，`agent_run_stream` 会 `cancel` 生产者任务。工作线程里的 `run_loop` 停不下来，上游调用会继续跑完。`agent_service.py` 里已经留了注释：给 `run_loop` 加 `threading.Event`，每轮开头检查。

`USAGE` 仍是 `trace.py` 里的进程级字典。SSE 没有把它推给客户端，所以这次输出不受影响。两个请求同时跑时，这个字典会串数。
