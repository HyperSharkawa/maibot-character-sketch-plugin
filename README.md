# maibot-character-sketch-plugin
MaiBot 的人物画像插件，通过分析聊天记录，用 LLM 为群友生成详细的人格画像。

## 功能
- **人格画像生成**：通过指令 `画像 [目标用户]`，插件会收集目标用户的聊天记录及其上下文，调用 LLM 生成深度人格分析。
- **上下文感知**：不仅分析目标用户的发言，还会结合其发言前后的上下文消息，确保画像更加准确、立体。
- **灵活配置**：支持自定义检索消息数量、上下文长度、单条消息最大字数限制、提示词等。
- **权限控制（黑白名单）**：支持白名单 / 黑名单两种模式，并可配置管理员跨聊天流查询权限。

## 安装
1. 将仓库克隆到麦麦的 `plugins` 目录：
   ```powershell
   cd <maibot 根目录>\plugins
   git clone https://github.com/HyperSharkawa/maibot-character-sketch-plugin
   ```
2. 重启麦麦，插件会在启动日志中以 `character_sketch_plugin` 名称出现，并自动生成配置文件。

### 基础配置 (`character_sketch_plugin`)

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `context_length` | `int` | `3` | 为目标用户画像时给LLM提供的**上文**信息条数。注意：上下文也会占用总消息数额度。 |
| `context_length_after` | `int` | `1` | 为目标用户画像时给LLM提供的**下文**信息条数。 |
| `max_message_count` | `int` | `700` | 最终发送给 LLM 的最大消息条数（包含上下文）。请注意 Token 消耗。 |
| `retrieval_message_count` | `int` | `30000` | 从数据库中检索的历史消息总数。 |
| `max_message_length` | `int` | `200` | 单条消息的最大字数限制。超过此限制的消息将被截断并标记。`0` 表示不限制。 |
| `prompt_template` | `string` | (内置模板) | 生成画像时使用的提示词模板。支持变量：`{person_name}`, `{user_nickname}`, `{messages}` 等，详见配置文件。 |

### 模型配置 (`llm_config`)

| 字段 | 类型 | 说明 | 默认值 |
| --- | --- | --- | --- |
| `llm_group` | `string` | 使用的 LLM 分组（如 `utils`, `replyer`）。仅当 `llm_list` 为空时生效。 | `"utils"` |
| `llm_list` | `list[string]` | **优先使用**。指定具体的模型名称列表。建议使用长窗口模型。 | `["gemini-2.5-pro", ...]` |
| `max_tokens` | `int` | 模型输出的最大 Token 数。 | `20000` |
| `temperature` | `float` | 模型温度，控制生成随机性。 | `0.7` |
| `slow_threshold` | `float` | 慢请求阈值（秒），超时记录警告日志。 | `30` |
| `selection_strategy` | `string` | 模型选择策略：`balance` (负载均衡) 或 `random` (随机)。 | `"balance"` |

### 权限配置 (`permissions`)

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `permission_mode` | `string` | `"blacklist"` | 权限模式：`whitelist`（仅列表内可用）或 `blacklist`（列表内禁用，其他可用）。 |
| `user_id_list` | `list[object]` | `[{"user_id":"1234567890","description":"示例用户"}]` | 用户列表。会根据 `permission_mode` 决定“允许名单”或“禁止名单”。description` 为可选的备注说明，仅用于查看，不影响功能。 |
| `admin_id_list` | `list[string]` | `["1234567890"]` | 管理员用户ID列表。管理员可跨聊天流查询画像。 |

> 注意：当 `permission_mode = "whitelist"` 且 `user_id_list` 为空时，插件会拒绝所有用户使用画像命令！

> ⚙️ 修改配置后需重启生效。请根据你能接受的 Token 消耗和 LLM 上下文窗口调整 `max_message_count` 和 `context_length`。

## 使用说明
- **触发方式**：在群聊中发送 `#画像` 或 `/画像`。
- **指定对象**：
  - `#画像 @某人`：为被艾特的用户生成画像。
  - `#画像 <人物名称>`：为该人物名称的用户生成画像。
  - `#画像`（无参数）：为发送指令的用户自己生成画像。
- **进阶用法**：
  - 管理员可以使用 `#画像 <用户> <聊天ID(私聊为对方QQ号，群聊为群号)>` 跨聊天流获取画像。
  - *普通用户仅限获取当前聊天流画像，不能跨聊天流。*
  
- **生成过程**：
  1. 插件检索指定范围内的历史消息。
  2. 筛选目标用户的发言，并按配置补充前后上下文。
  3. 对过长消息进行截断处理。
  4. 将整理好的对话记录发送给 LLM。
  5. LLM 返回分析结果，Bot 发送回群聊。

## 常见问题
- **生成的画像不准确**：
  - 尝试增加 `max_message_count` 提供更多聊天数据。
  - 检查 `prompt_template` 是否符合你的需求，可自行调整 Prompt 让 AI 关注特定方面。
- **报错“未找到可用的模型配置”**：
  - 请检查 `llm_config.llm_list` 中的模型名称是否在 MaiBot 后台已添加。
  - 若使用分组，请确认 `llm_group` 对应的分组有可用模型。
- **未找到消息记录**：目标用户在当前群聊中发言过少，或 `retrieval_message_count` 设置过小。
- **发送命令没有任何回复或提示“没有使用该命令的权限”**：请检查 `permissions.permission_mode` 与 `permissions.user_id_list` 是否符合预期；若白名单为空则会拒绝所有用户。
- **发送命令后Bot长时间无响应，且在后台中出现与平台断开连接的日志**: 查找和整理聊天记录的过程是阻塞的，如果服务器配置不高或聊天记录过多，可能会发生这种情况。请尝试降低 `max_message_count` 和 `retrieval_message_count` 。
- **画像生成失败**：检查 LLM 连接状态或 API 额度，查看日志获取详细错误信息。

## 免责声明
本插件仅供娱乐和交流使用。
- **AI 生成内容**：所有“人格画像”均由人工智能模型基于群聊历史记录自动生成，不代表真实的人物评价。
- **非专业建议**：生成结果仅供参考，**绝不构成**任何形式的心理咨询、医疗诊断或专业建议。
- **使用须知**：请勿将生成结果用于严肃的心理评估、人身攻击或其他非法用途。开发者不对生成内容的准确性、完整性或因使用本插件而产生的任何后果负责。