# learning-mentor 技能组

从一次完整的「路线图 → 逐讲指导 → 验收 → 阶段博客」会话中提炼的导师流程，拆成五个 Cursor 技能：

| 技能 | 作用 | 触发 |
|---|---|---|
| `learning-mentor` | 总流程：状态机、铁律、状态文件、防衰减措施 | 任何学习/指导/验收类请求先读 |
| `learning-mentor-roadmap` | 建路线图，产出 `learning/ROADMAP.md` 与 `learning/PROGRESS.md` | 「我想学 X」「规划一下」 |
| `learning-mentor-lecture` | 写一讲：问题、设计、完整代码、讲解、验收、记录模板 | 「指导我做 Phase N」「下一讲」 |
| `learning-mentor-review` | 验收一讲：读全部产物、独立复现、写记录、给结论与修复 | 贴输出 /「我做完了」/「请验收」 |
| `learning-mentor-wrapup` | 阶段收尾：博客 + 方法论讲解、复盘、更新路线图、预热下一阶段 | 「写博客」「复盘」「更新路线图」 |

## 安装到其他项目或工具

- **Cursor（项目级）**：把 `learning-mentor*` 五个目录复制到目标仓库的 `.cursor/skills/`。
- **Cursor（用户级）**：复制到 `~/.cursor/skills/`，所有项目可用。
- **其他 Agent 工具**：每个 `SKILL.md` 自包含（模板都内嵌，无外部引用），可直接作为系统提示词片段或规则文件使用；保留 frontmatter 里的 `description`，它是触发条件。

## 开始使用

在目标仓库里对 AI 说「我想学 X，用 learning-mentor 流程帮我规划」。它会先盘点仓库、建 `learning/` 目录，之后每个回合从 `learning/PROGRESS.md` 的状态出发。
