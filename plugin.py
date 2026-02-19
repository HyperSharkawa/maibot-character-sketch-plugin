from typing import List, Tuple, Type

from src.common.logger import get_logger
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField
)
from .components.portrayal_command import PortrayalCommand

logger = get_logger("character_sketch_plugin")


@register_plugin
class PortrayalPlugin(BasePlugin):
    # 插件基本信息
    plugin_name: str = "character_sketch_plugin"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表
    config_file_name: str = "config.toml"  # 配置文件名
    config_section_descriptions = {
        # 插件基础配置
        "character_sketch_plugin": "画像插件配置",
        # llm配置
        "llm_config": "LLM模型配置",
        # 权限设置
        "permissions": "权限设置，定义哪些用户可以使用插件功能",
    }  # 配置文件各节描述
    config_schema = {
        "character_sketch_plugin": {
            # 给llm提供的前面的上下文信息条数 进行生成时会把目标用户的消息之前取这么多条作为上下文
            "context_length": ConfigField(
                type=int,
                default=3,
                description="为目标用户画像时给llm提供的上文信息条数，目标用户消息前面的指定条数的消息也会被加入到提示词中。注意，上下文也会占用消息数，这会减少目标用户的消息数量",
            ),
            # 给llm提供的后面的上下文信息条数 进行生成时会把目标用户的消息之后取这么多条作为上下文
            "context_length_after": ConfigField(
                type=int,
                default=1,
                description="为目标用户画像时给llm提供的下文信息条数，目标用户消息后面的指定条数的消息也会被加入到提示词中。注意，上下文也会占用消息数，这会减少目标用户的消息数量",
            ),
            # 生成用户画像时使用的最大消息记录条数，包含上下文消息
            "max_message_count": ConfigField(
                type=int,
                default=700,
                description="生成用户画像时使用的最大消息记录条数，包含上下文消息。请注意性能消耗、token消耗和模型最大token限制！",
            ),
            # 生成用户画像时检索的最大消息记录条数 （用于从数据库中获取消息，之后会进行清洗以符合portrayal_max_message_count的要求）
            "retrieval_message_count": ConfigField(
                type=int,
                default=30000,
                description="生成用户画像时检索的最大消息记录条数。用于从数据库中读取消息并从中筛选。请注意性能消耗",
            ),
            # 生成画像时的单条消息最大字数限制，超过这个字数的消息会被截断 0表示不限制
            "max_message_length": ConfigField(
                type=int,
                default=200,
                description="生成画像时的单条消息最大字数限制，超过这个字数的消息会被截断。0表示不限制。",
            ),
            # 生成用户画像时使用的提示词
            # 支持变量：
            # 用户昵称:{person_name}
            # 用户QQ昵称:{user_nickname}
            # 消息数量 {message_count}
            # 消息内容 {messages}
            # 上文消息数量 {context_length}
            # 下文消息数量 {context_length_after}
            "prompt_template": ConfigField(
                type=str,
                input_type="textarea",
                default="# Role\n你是一位拥有敏锐洞察力的资深心理侧写师和AI人格架构师。你擅长通过零散的聊天记录，精准捕捉人物的性格底色、说话习惯和社交属性。你的分析既专业又带有娱乐性，能够通过字里行间发现用户的“灵魂本质”。\n\n# Context\n我需要你分析群聊用户「{person_name}」（QQ昵称：{user_nickname}）。\n为了帮助你理解语境，我提供了该用户发送的消息，以及每条消息前 {context_length} 条和后 {context_length_after} 条的上下文消息。\n**注意**：\n1. 聊天记录中的图片已被过滤，请忽略图片缺失带来的影响。\n2. 聊天记录有限，请关注**重复出现的模式**（如口癖、情绪倾向、对待他人的态度），避免因单句脱离语境的发言而产生“过拟合”的误判。\n3. 区分“目标用户发言”与“他人发言”，他人发言仅作为理解语境的参考。\n\n# Task\n请基于提供的聊天记录，完成以下两个任务：\n\n## 任务一：全方位用户画像 (Profile Analysis)\n请生成一份详细的分析报告，包含以下维度：\n1.  **核心性格 (MBTI推测)**：推测其MBTI倾向，并用3个关键词概括性格（如：傲娇、老好人、乐子人）。\n2.  **语言风格 (Linguistic Style)**：分析其用词习惯、标点使用（是否爱用波浪号、句号等）、常用梗、语气助词（如：捏、喵、卧槽）。\n3.  **社交生态 (Social Role)**：在群里的定位（如：群主、潜水员、话题终结者、复读机、捧哏）。\n4.  **兴趣与能力 (Interests & Abilities)**：根据聊天内容推断其爱好、擅长的领域或经常讨论的话题。\n5.  **潜在弱点/槽点 (Roast)**：以幽默/调侃的语气指出该用户的一个可爱缺点或槽点。\n\n## 任务二：AI克隆指令\n基于以上分析，使用中文编写一段**高质量的System Prompt**，用于指导另一个AI完美扮演该用户。该Prompt应该包含人物设定、对话规则。\n\n# Input Data\n--- 聊天记录开始 ---\n{messages}\n--- 聊天记录结束 ---\n\n# Output Requirement\n请先输出【任务一】的分析结果，风格要生动、幽默，符合娱乐向定位。\n然后在一个 **Markdown代码块** 中输出【任务二】的Prompt。",
                description="生成用户画像时使用的提示词 支持变量：用户昵称 {person_name} 用户QQ昵称 {user_nickname} 消息数量 {message_count} 消息内容 {messages} 上文消息数量 {context_length} 下文消息数量 {context_length_after}",
            ),
        },
        "llm_config": {
            # 生成用户画像时使用的LLM模型分组
            "llm_group": ConfigField(
                type=str,
                choices=['lpmm_entity_extract', 'lpmm_rdf_build', 'planner', 'replyer', 'tool_use', 'utils', 'vlm'],
                default="utils",
                description="生成用户画像时使用的LLM模型分组 懒得设置的话在这选一个就能用。下面的设置对该处选择的模型不生效，从这选的模型在webui的“为模型分配功能”中设定。如果想详细配置请在下方手动配置",
            ),
            # 生成用户画像使用的模型名称 会优先使用该处设置，当此处为空时会使用LLM模型分组中指定的模型
            "llm_list": ConfigField(
                type=list,
                item_type="string",
                default=["gemini-2.5-pro", "glm-4.7", "LongCat-Flash-Thinking"],
                description="生成用户画像使用的模型名称(你在模型管理中添加的模型的名称)。当此处不为空时会使用此处设定的模型，否则使用LLM模型分组中指定的模型",
            ),
            # 生成用户画像时使用的模型的最大输出token数
            "max_tokens": ConfigField(
                type=int,
                default=20000,
                description="生成用户画像时使用的模型的最大输出token数，仅对手动设置的模型生效 请根据实际情况设置，避免超过模型限制",
            ),
            # 生成用户画像时使用的模型的温度
            "temperature": ConfigField(
                type=float,
                default=0.7,
                description="生成用户画像时使用的模型的温度，仅对手动设置的模型生效",
            ),
            # 生成用户画像时使用的模型的慢请求阈值 单位秒，超过该时间会输出警告日志
            "slow_threshold": ConfigField(
                type=float,
                default=30,
                description="生成用户画像时使用的模型的慢请求阈值，单位秒，超过该时间会输出警告日志。仅对手动设置的模型生效",
            ),
            # 生成用户画像时使用的模型的选择策略 balance（负载均衡）或 random（随机选择）
            "selection_strategy": ConfigField(
                type=str,
                choices=['balance', 'random'],
                default="balance",
                description="生成用户画像时使用的模型的选择策略，仅对手动设置的模型生效 balance（负载均衡）或 random（随机选择）",
            ),
        },
        "permissions": {
            # 管理员用户ID列表，能查看所有聊天流的画像
            "admin_id_list": ConfigField(
                type=list,
                item_type="string",
                default=["1234567890"],
                description="管理员用户ID列表，能查看所有聊天流的画像",
            ),
            # 权限模式，可选：白名单、黑名单。
            "permission_mode": ConfigField(
                type=str,
                choices=['whitelist', 'blacklist'],
                default="blacklist",
                description="权限模式，可选：白名单、黑名单。白名单模式下，只有在列表中的用户可以使用插件功能；黑名单模式下，除了在列表中的用户，其他用户都可以使用插件功能",
            ),
            # 用户ID列表，根据权限模式决定是允许还是禁止使用插件功能的用户列表
            "user_id_list": ConfigField(
                type=list,
                item_type="object",
                item_fields={
                    "user_id": {
                        "type": "string",
                        "label": "用户的QQ号",
                        "placeholder": "用户的QQ号"
                    },
                    "description": {
                        "type": "string",
                        "label": "描述",
                        "placeholder": "可选，对该用户的简短描述，仅便于查看，不会影响功能"
                    },
                },
                default=[{"user_id": "1234567890", "description": "示例用户"}],
                description="用户ID列表，根据权限模式决定是允许还是禁止使用插件功能的用户列表",
            ),
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        permission_mode: str = self.config.get("permissions", {}).get("permission_mode", "blacklist")
        user_id_list = self.config.get("permissions", {}).get("user_id_list", [])
        user_id_list = [item["user_id"] for item in user_id_list if "user_id" in item]
        admin_id_list = self.config.get("permissions", {}).get("admin_id_list", [])
        if permission_mode not in ["whitelist", "blacklist"]:
            logger.warning(f"权限模式设置为 {permission_mode}，但这不是一个有效的权限模式。请检查配置并设置为 'whitelist' 或 'blacklist'。默认将使用黑名单模式")
            permission_mode = "blacklist"
        if permission_mode == "whitelist" and not user_id_list:
            logger.warning("权限模式为白名单，但用户ID列表为空，这将导致没有用户可以使用插件功能！")
        PortrayalCommand.permission_mode = permission_mode
        PortrayalCommand.user_id_list = user_id_list
        PortrayalCommand.admin_id_list = admin_id_list
        return [
            (PortrayalCommand.get_command_info(), PortrayalCommand),
        ]
