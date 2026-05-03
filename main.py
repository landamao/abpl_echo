import asyncio
from astrbot.api.event import filter
from astrbot.api.all import Star, Context, logger, Plain, Reply, AstrBotConfig, MessageChain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

class 复读器(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        # 原有配置
        复读设置:dict = config['复读设置']
        self.复读机: bool = 复读设置['复读机']
        self.复读阈值 = 复读设置['复读阈值']
        self.复读模式:str = 复读设置['复读模式']
        self.打断内容:str = 复读设置['打断内容']
        指令设置:dict = config['指令设置']
        self.a = not 指令设置['发送']
        self.b = not 指令设置['复读']
        self.c = not 指令设置['撤回']
        self.群消息:dict[str, dict] = {}

        # 新增配置
        自动撤回设置:dict = config['自动撤回设置']
        self.自动撤回:bool = 自动撤回设置['自动撤回']   # 是否启用自动撤回
        self.延迟时间 = 自动撤回设置['延迟时间']   # 撤回延迟秒数
        # 管理撤回任务
        self.撤回任务 = set()
        logger.debug(self.__dict__)

    def 移除任务(slef, 任务: asyncio.Task):
        """任务完成时从集合中移除"""
        slef.撤回任务.discard(任务)

    @staticmethod
    async def 延迟撤回(bot, 消息ID: int, 延迟时间: int):
        """延迟撤回消息"""
        await asyncio.sleep(延迟时间)
        try:
            if 消息ID:
                await bot.delete_msg(message_id=消息ID)
                logger.info(f"✅ 已自动撤回消息，ID: {消息ID}")
        except Exception as e:
            logger.error(f"❌ 撤回消息失败: {e}")

    async def 发送消息(slef, event: AiocqhttpMessageEvent, chain: list):
        """
        发送消息并处理自动撤回逻辑
        :param event: 消息事件
        :param chain: 要发送的消息链（MessageComponent 列表）
        """

        # 将消息链转换为 OneBot 格式
        onebot消息 = await event._parse_onebot_json(MessageChain(chain=chain))
        if not onebot消息:
            logger.warning("待发送消息为空，跳过")
            return

        # 发送消息
        try:
            if 群号 := event.get_group_id():
                结果 = await event.bot.call_action(
                    "send_group_msg",
                    group_id=int(群号),
                    message=onebot消息
                )
            else:
                结果 = await event.bot.call_action(
                    "send_private_msg",
                    user_id=int(event.get_sender_id()),
                    message=onebot消息
                )
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return

        # 获取消息 ID
        消息ID = 结果.get("message_id") if isinstance(结果, dict) else None
        if not 消息ID:
            logger.error(f"无法获取消息 ID，自动撤回失效：\n{结果}")
            return

        logger.info(f"📤 消息发送成功，ID: {消息ID}")

        # 如果启用了自动撤回，安排任务
        if slef.自动撤回 and slef.延迟时间 > 0:
            任务 = asyncio.create_task(
                slef.延迟撤回(event.bot, int(消息ID), slef.延迟时间)
            )
            任务.add_done_callback(slef.移除任务)
            slef.撤回任务.add(任务)
            logger.info(f"⏰ 已安排 {slef.延迟时间} 秒后撤回消息 {消息ID}")

    @filter.command("发送", alias={"发", "文本"})
    async def 发送文本(slef, event: AiocqhttpMessageEvent, 文本: str = ""):
        """将用户输入的内容原样发送出去，指令：/发送 内容"""
        if (slef.a or event.is_admin()) and 文本:
            消息链 = event.get_messages()
            for seg in 消息链:
                if isinstance(seg, Plain):
                    # 去掉命令前缀，保留剩余内容
                    seg.text = ''.join(seg.text.split(maxsplit=1)[1:])
                    break
            # 使用新的发送方法（带自动撤回）
            await slef.发送消息(event, 消息链)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=666)
    async def 监听消息(slef, event: AiocqhttpMessageEvent):
        """复读or撤回引用的消息，引用消息后输入“复读”即可复读；输入“撤回”可撤回引用的消息"""
        if not (消息链 := event.get_messages()):
            return

        纯净文本 = next((组件.text for 组件 in 消息链 if isinstance(组件, Plain)), '').strip()
        if 纯净文本 == '复读':
            if slef.b or event.is_admin():
                event.stop_event()
                for 组件 in 消息链:
                    if isinstance(组件, Reply):
                        复读消息链 = 组件.chain  # 获取嵌套的消息链
                        # 使用新的发送方法（带自动撤回）
                        await slef.发送消息(event, 复读消息链)
                        break
            return
        elif 纯净文本 == '撤回':
            if slef.c or event.is_admin():
                event.stop_event()
                for 组件 in 消息链:
                    if isinstance(组件, Reply):
                        消息ID = 组件.id
                        try:
                            await event.bot.delete_msg(message_id=消息ID)
                            logger.info(f"✅ 已撤回消息，ID: {消息ID}")
                        except Exception as e:
                            logger.error(f"❌ 撤回消息失败: {e}")
                        break
            return

        if slef.复读机 and (群号 := event.get_group_id()):
            if not (len(消息链) == 1 and isinstance(消息链[0], Plain)):
                slef.群消息.pop(群号, None)
                return
            纯文本 = event.get_message_str()
            qq = event.get_sender_id()
            if 群号 in slef.群消息:
                信息 = slef.群消息[群号]
                if 纯文本 == 信息['文本']:
                    if qq in 信息['qq']:
                        return  # 同一个人，不再处理
                    信息['次数'] += 1
                    信息['qq'].append(qq)
                    if 信息['次数'] == slef.复读阈值:
                        if slef.复读模式 == "跟着复读":
                            yield event.plain_result(纯文本)
                        else:
                            yield event.plain_result(slef.打断内容)
                    return
            slef.群消息[群号] = {'文本': 纯文本, '次数': 1, 'qq': [qq]}

    async def terminate(slef):
        """当插件被禁用、重载插件时会调用这个方法"""
        for 任务 in slef.撤回任务:
            if not 任务.done():
                任务.cancel()
        if slef.撤回任务:
            await asyncio.gather(*slef.撤回任务, return_exceptions=True)
        slef.撤回任务.clear()
        logger.info("复读器插件被禁用/重载，所有撤回任务已取消")