# 📢 复读器

> 让机器人帮你发消息、复读、撤回，并支持自动撤回。

## 🚀 怎么用

**1. 发送文字**
```
/发送 你好呀
```
（也可用 `/发` 或 `/文本`）

--- 
**2. 复读消息**
- 引用一条消息，然后输入：
```
复读
```

#### 示例
<img src="https://img.remit.ee/api/file/BQACAgUAAyEGAASHRsPbAAET3BRp9z3uI77hD29AiYM_oy7Asvlu8gACtyEAAoHJwFeVgNBBB7c3_TsE.jpg" width="300">

---

**3. 撤回消息**
- 引用一条消息，然后输入：
```
撤回
```

#### 示例
<img src="https://img.remit.ee/api/file/BQACAgUAAyEGAASHRsPbAAET3B5p90ADV2jXNPGt238G_Fvn1NUFGQACwSEAAoHJwFcaIMgbPfKYKTsE.jpg" width="300">

---

**4. 自动复读机**
群内不同人连续发多条相同内容，机器人自动复读。

**5. 自动撤回**
机器人自己发的消息（通过 `/发送` 或 `复读`）会在设定秒数后自动消失。

## ⚠️ 注意事项

1. **自动撤回仅对本插件发送的消息生效**（即 `/发送` 和 `复读` 命令产生的消息），不会撤回其他消息。
2. 撤回功能需要机器人拥有 **删除消息** 的权限（群管理员或授权）。
3. 插件被禁用或重载时，所有未执行的自动撤回任务会被自动取消。