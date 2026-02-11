import time
from typing import List, Tuple, Optional

from maim_message import Seg

from src.common.logger import get_logger
from src.config.api_ada_configs import TaskConfig
from src.config.config import global_config
from src.config.config import model_config as global_model_config
from src.plugin_system import (
    BaseCommand,
    llm_api,
    person_api
)
from ..utils import get_messages_by_user_in_stream, prepare_portrayal_messages, filter_messages_with_context, \
    resolve_stream_id

logger = get_logger("character_sketch_plugin")


class PortrayalCommand(BaseCommand):
    """
    画像Command - 响应/画像命令

    1. 获取触发命令的消息是否@了别人，如果有@别人则画像对象为被@的人，否则画像对象为命令发送者自己
    2. 获取画像对象在当前聊天流最近的指定数量的消息记录
    3. 整理消息记录，调用LLM生成用户画像
    """

    command_name = "画像"
    command_description = "根据用户的聊天记录生成用户画像"

    # === 命令设置（必须填写）===
    command_pattern = r"^[/#]画像(\s*(?P<name>\S+))?(\s+(?P<chat_id>\S+))?"

    async def execute(self) -> Tuple[bool, Optional[str], int]:
        """执行画像命令"""
        admin_user_ids = self.get_config("character_sketch_plugin.admin_user_ids", [])
        is_admin = self.message.message_info.user_info.user_id in admin_user_ids
        prompt_template = self.get_config("character_sketch_plugin.prompt_template", None)
        llm_list = self.get_config("llm_config.llm_list", [])

        if llm_list:
            model_config = TaskConfig()
            model_config.model_list = llm_list
            model_config.max_tokens = self.get_config("llm_config.max_tokens", 20000)
            model_config.temperature = self.get_config("llm_config.temperature", 0.7)
            model_config.slow_threshold = self.get_config("llm_config.slow_threshold",30)
            model_config.selection_strategy = self.get_config("llm_config.selection_strategy", "balance")
        else:
            llm_group = self.get_config("llm_config.llm_group", "utils")
            models = llm_api.get_available_models()
            model_config = models.get(llm_group)
            if not model_config:
                logger.error(f"未找到可用的 {llm_group} 模型配置")
                return True, f"未找到可用的 {llm_group} 模型配置", True
        if not prompt_template:
            logger.error("画像提示词为空")
            return True, "画像提示词为空", True
        target_user_id, person_name, nickname, stream_id = await self.get_portrayal_target()
        logger.debug(f"画像对象用户ID: {target_user_id}, 昵称: {nickname}, 聊天流ID: {stream_id}")
        if not target_user_id:
            await self.send_text("未能确定画像对象的用户ID，请检查命令格式或@的用户信息。")
            return True, f"", True

        start_time = time.time() - 24 * 3600 * 30
        end_time = time.time()
        if not stream_id and not is_admin:
            # 如果没有指定聊天流ID，则将会搜索所有聊天流中该用户的消息 该功能仅限管理员使用
            await self.send_text("你没有使用该参数的权限")
            return True, f"", True
        if stream_id != self.message.chat_stream.stream_id and not is_admin:
            await self.send_text("你没有使用该参数的权限")
            return True, f"", True
        retrieval_message_count = self.get_config("character_sketch_plugin.retrieval_message_count",
                                                  50000)
        context_length = self.get_config("character_sketch_plugin.context_length", 10)
        context_length_after = self.get_config("character_sketch_plugin.context_length_after", 3)
        max_message_count = self.get_config("character_sketch_plugin.max_message_count", 500)
        max_message_length = self.get_config("character_sketch_plugin.max_message_length", 200)

        # 获取用户在指定聊天流中的消息记录
        messages = get_messages_by_user_in_stream([], start_time, end_time, stream_id,
                                                  retrieval_message_count)
        retrieval_message_count = len(messages)
        # 过滤出画像对象的消息和上下文消息
        messages = filter_messages_with_context(
            messages,
            target_user_id,
            context_length,
            context_length_after,
            max_message_count * 2
        )
        # 删除对画像生成无用的信息并整理消息内容为字符串列表
        lines, primary_count, other_count = await prepare_portrayal_messages(
            messages,
            max_message_count,
            primary_user_id=target_user_id,
            person_name_dict={
                target_user_id: person_name,
                global_config.bot.qq_account: global_config.bot.nickname
            },
            max_message_length=max_message_length
        )
        if not messages:
            await self.send_text(f"未找到用户 {person_name} 的消息记录，无法生成画像。")
            return True, f"", True
        if not lines:
            await self.send_text(f"未找到有效的消息内容，无法生成画像。")
            return True, f"", True

        await self.send_text(
            f"使用了 {len(lines)} 条历史消息，其中目标用户 {primary_count} 条，上下文 {other_count} 条。正在生成画像，请稍候...")

        prompt = prompt_template.format(
            person_name=person_name,
            user_nickname=nickname,
            messages="\n".join(lines),
            context_length=context_length,
            context_length_after=context_length_after,
            message_count=len(messages)
        )
        success, response, _, _ = await llm_api.generate_with_model(prompt, model_config=model_config)
        if not success:
            logger.error(f"模型响应失败: {response}")
            return True, f"", True

        message_body: Tuple[str, str] = ("text", response)
        message: Tuple[str, str, List[Tuple[str, str]]] = (
            global_config.bot.qq_account, global_config.bot.nickname, [message_body]
        )
        await self.send_forward([message])

        return True, f"", True

    async def get_portrayal_target(self) -> Tuple[str, str, str, str]:
        """
        获取画像目标用户ID
        returns: Tuple[str, str, str]: 画像目标的用户ID、人物名称、QQ昵称、聊天流ID
        """
        name = self.matched_groups.get("name", "")
        chat_id = self.matched_groups.get("chat_id", "")
        if isinstance(name, str): name = name.strip()
        if isinstance(chat_id, str): chat_id = chat_id.strip()
        if not chat_id:
            logger.debug(f"未指定聊天流ID，使用当前聊天流ID: {self.message.chat_stream.stream_id}")
            chat_id = self.message.chat_stream.stream_id
        elif chat_id == "全部":
            logger.debug("命令参数指定搜索所有聊天流")
            chat_id = ""  # 返回空字符串表示搜索所有聊天流
        else:
            logger.debug(f"命令参数指定聊天流ID: {chat_id}")
            stream_id = resolve_stream_id(chat_id)
            if not stream_id:
                logger.warn(f"无法根据命令参数指定的聊天ID找到对应的聊天流: “{chat_id}” 使用当前聊天流ID")
                chat_id = self.message.chat_stream.stream_id
            else:
                chat_id = stream_id

        if name and not name.startswith("@<"):
            # 如果命令中指定了名字，则根据名字获取用户ID
            logger.info(f"根据命令参数指定的名字获取画像对象: {name}")
            person_id = person_api.get_person_id_by_name(name)
            target_user_id = await person_api.get_person_value(person_id, "user_id")
            nickname = await person_api.get_person_value(person_id, "nickname")
            return target_user_id, name, nickname, chat_id

        # 通过@提取用户ID
        # 整理消息分段
        segments: List[Seg]
        if self.message.message_segment.type == "seglist":
            segments = self.message.message_segment.data
        else:
            segments = [self.message.message_segment]

        # 从所有分段中提取被 @ 的用户ID
        at_user_ids: List[str] = []
        seg: Seg
        for seg in segments:
            logger.info(seg.data)
            if seg.type != "text":
                continue
            data = seg.data
            if not isinstance(data, str) or not data.startswith("@"):
                continue
            # @的格式为 "@<用户昵称:数字形式的user_id>"
            data = data.strip("@<>")
            parts = data.split(":")
            if len(parts) < 2:
                continue
            user_id = parts[-1]
            at_user_ids.append(user_id.strip())

        # 已经获取到了被 @ 的用户ID列表
        if at_user_ids:
            # 如果有被 @ 的人，只取第一个
            target_user_id = at_user_ids[0]
        else:
            # 否则画像对象为发送者自己
            target_user_id = self.message.message_info.user_info.user_id
        if target_user_id == global_config.bot.qq_account:
            # 如果画像对象是机器人自己，则将画像对象设为发送者自己
            target_user_id = self.message.message_info.user_info.user_id
        person_id = person_api.get_person_id('qq', target_user_id)
        person_name = await person_api.get_person_value(person_id, "person_name")
        nickname = await person_api.get_person_value(person_id, "nickname")
        return target_user_id, person_name, nickname, chat_id
