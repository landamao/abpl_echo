import asyncio
from astrbot.api.event import filter
from astrbot.api.all import Star, Context, logger, Plain, Reply, AstrBotConfig, MessageChain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

class 复读器(Star):
    def __init__(s, context: Context, config: AstrBotConfig):
        super().__init__(context)
        # 原有配置
        s.a = not config.发送
        s.b = not config.复读
        s.c = not config.撤回
        s.d = config.复读机
        s.群消息 = {}

        # 新增复读模式配置
        s.repeat_mode = config.get("复读模式", "自定义内容")  # 跟着复读/自定义内容
        s.break_text = config.get("打断内容", "打断施法")  # 自定义打断内容

        # 新增配置
        s.auto_recall = config.自动撤回   # 是否启用自动撤回
        s.recall_time = config.延迟时间   # 撤回延迟秒数
        # 管理撤回任务
        s._recall_tasks = set()

    def _remove_task(s, task: asyncio.Task):
        """任务完成时从集合中移除"""
        s._recall_tasks.discard(task)

    @staticmethod
    async def _recall_msg(client, message_id: int, delay: int):
        """延迟撤回消息"""
        await asyncio.sleep(delay)
        try:
            if message_id:
                await client.delete_msg(message_id=message_id)
                logger.info(f"✅ 已自动撤回消息，ID: {message_id}")
        except Exception as e:
            logger.error(f"❌ 撤回消息失败: {e}")

    async def _send_with_recall(s, event: AiocqhttpMessageEvent, chain: list):
        """
        发送消息并处理自动撤回逻辑
        :param event: 消息事件
        :param chain: 要发送的消息链（MessageComponent 列表）
        """

        # 将消息链转换为 OneBot 格式
        onebot_msgs = await event._parse_onebot_json(MessageChain(chain=chain))
        if not onebot_msgs:
            logger.warning("待发送消息为空，跳过")
            return

        # 发送消息
        try:
            if group_id := event.get_group_id():
                result = await event.bot.call_action(
                    "send_group_msg",
                    group_id=int(group_id),
                    message=onebot_msgs
                )
            else:
                result = await event.bot.call_action(
                    "send_private_msg",
                    user_id=int(event.get_sender_id()),
                    message=onebot_msgs
                )
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return

        # 获取消息 ID
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if not message_id:
            logger.error("无法获取消息 ID，自动撤回失效")
            return

        logger.info(f"📤 消息发送成功，ID: {message_id}")

        # 如果启用了自动撤回，安排任务
        if s.auto_recall and s.recall_time > 0:
            task = asyncio.create_task(
                s._recall_msg(event.bot, int(message_id), s.recall_time)
            )
            task.add_done_callback(s._remove_task)
            s._recall_tasks.add(task)
            logger.info(f"⏰ 已安排 {s.recall_time} 秒后撤回消息 {message_id}")

    @filter.command("发送", alias={"发", "文本"})
    async def 文本(s, event: AiocqhttpMessageEvent, 文本: str = ""):
        """将用户输入的内容原样发送出去，指令：/发送 内容"""
        if (s.a or event.is_admin()) and 文本:
            消息链 = event.get_messages()
            for seg in 消息链:
                if isinstance(seg, Plain):
                    # 去掉命令前缀，保留剩余内容
                    seg.text = ''.join(seg.text.split(maxsplit=1)[1:])
                    break
            event.stop_event()
            # 使用新的发送方法（带自动撤回）
            await s._send_with_recall(event, 消息链)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=999)
    async def 复读(s, event: AiocqhttpMessageEvent):
        """复读or撤回引用的消息，引用消息后输入“复读”即可复读；输入“撤回”可撤回引用的消息"""
        if not (消息链 := event.get_messages()):
            return

        纯净文本 = next((seg.text for seg in 消息链 if isinstance(seg, Plain)), '').strip()
        if 纯净文本 == '复读':
            if s.b or event.is_admin():
                event.stop_event()
                for seg in 消息链:
                    if isinstance(seg, Reply):
                        复读消息链 = seg.chain  # 获取嵌套的消息链
                        # 使用新的发送方法（带自动撤回）
                        await s._send_with_recall(event, 复读消息链)
                        break
        elif 纯净文本 == '撤回':
            if s.c or event.is_admin():
                event.stop_event()
                for seg in 消息链:
                    if isinstance(seg, Reply):
                        消息ID = seg.id
                        try:
                            await event.bot.delete_msg(message_id=消息ID)
                            logger.info(f"✅ 已撤回消息，ID: {消息ID}")
                        except Exception as e:
                            logger.error(f"❌ 撤回消息失败: {e}")
                        break

        if s.d and event.get_group_id():
            if not (len(消息链) == 1 and isinstance(消息链[0], Plain)):
                s.群消息.pop(event.get_group_id(), None)
                return
            if event.get_group_id() in s.群消息:
                群消息 = s.群消息[event.get_group_id()]
                if event.get_message_str() == 群消息['text']:
                    if 群消息['zt'] and event.get_sender_id() != 群消息['usid']:
                        群消息['zt'] = False
                        # 根据配置选择复读或发送自定义内容
                        if s.repeat_mode == "跟着复读":
                            yield event.plain_result(event.get_message_str())
                        else:
                            yield event.plain_result(s.break_text)
                else:
                    群消息 = {'text': event.get_message_str(), 'usid': event.get_sender_id(),'zt': True}
                    s.群消息[event.get_group_id()] = 群消息
            else:
                群消息 = {'text': event.get_message_str(), 'usid': event.get_sender_id(),'zt': True}
                s.群消息[event.get_group_id()] = 群消息

    async def terminate(s):
        """当插件被禁用、重载插件时会调用这个方法"""
        for task in s._recall_tasks:
            if not task.done():
                task.cancel()
        if s._recall_tasks:
            await asyncio.gather(*s._recall_tasks, return_exceptions=True)
        s._recall_tasks.clear()
        logger.info("复读器插件被禁用/重载，所有撤回任务已取消")