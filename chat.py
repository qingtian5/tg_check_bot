from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import json
import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram.ext import ContextTypes

import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from telegram.ext import ConversationHandler

WAITING_FOR_USER_ID = 1


DB_PATH = "/root/data/disk/my_database.db"
TABLE_NAME = "users"

CONVERT_DATA = {
    "A": "鸽子",
    "B": "桩基",
    "C": "偷抢",
    "D": "阳痿",
    "E": "垃圾课",
    "F": "迟、拖",
}



# /start 命令
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or "无"
    full_name = user.full_name

    welcome_message = (
        f"你好 {full_name}！\n\n"
        f"📌 你的信息：\n"
        f"🆔 用户 ID: {user_id}\n"
        f"👤 用户名: @{username}"
    )

    print("=" * 50)
    print(welcome_message)
    print("=" * 50)

    await update.message.reply_text(welcome_message)


## 手动标记用户
async def trigger_manual_mark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 请输入你要标记的用户 ID：")
    return WAITING_FOR_USER_ID


async def handle_user_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 确保是回复机器人的提示
    if not update.message.reply_to_message or update.message.reply_to_message.from_user.id != context.bot.id:
        return  # 忽略不相关的输入

    user_input = update.message.text.strip()
    try:
        user_id = int(user_input)
    except ValueError:
        await update.message.reply_text("❌ 用户 ID 应该是纯数字，请重新输入。")
        return

    context.user_data["target_user_id"] = user_id
    context.user_data["manual_query"] = True

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"SELECT A, B, C, D, E, F FROM {TABLE_NAME} WHERE id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        summary = "\n".join([f"{CONVERT_DATA[chr(65+i)]} X {value}" for i, value in enumerate(row)])
        await update.message.reply_text(
            f"🔎 查到用户 ID: {user_id} 的标记信息：\n\n{summary}"
        )
    else:
        await update.message.reply_text(f"⚠️ 用户 ID {user_id} 未被标记过。")

    keyboard = [[InlineKeyboardButton("✅ 标记", callback_data=f"manual_mark:{user_id}")]]
    await update.message.reply_text("👇 选择操作：", reply_markup=InlineKeyboardMarkup(keyboard))

    return ConversationHandler.END




## 收到转发消息
async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    forward_origin = message.forward_origin

    if forward_origin and hasattr(forward_origin, "sender_user"):
        original_user = forward_origin.sender_user
        user_id = original_user.id
        username = original_user.username if original_user.username else '无'

        context.user_data["target_user_id"] = user_id
        context.user_data["target_username"] = username

        # 查询数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"SELECT A, B, C, D, E, F FROM {TABLE_NAME} WHERE id=?", (user_id,))
        rows = cursor.fetchall()
        conn.close()

        if rows:
            for row in rows:
                result = "\n".join([f"{CONVERT_DATA[chr(65+i)]} X {value}" for i, value in enumerate(row)])

            await message.reply_text(
                f"📌 原始用户信息：\n"
                f"🆔 用户 ID: {user_id}\n"
                f"👤 用户名: @{username}\n"
                f"📝 名字: {original_user.full_name}\n\n"
                f"📄 标记信息如下：\n{result}"
            )
        else:
            await message.reply_text(f"⚠️ 用户 @{username} (用户 ID {user_id}) 未被标记过。")

        keyboard = [[
            InlineKeyboardButton(
                "✅ 标记", 
                callback_data=f"mark:{message.from_user.id}:{user_id}:{username}"
            )
        ]]
        await message.reply_text("👇 选择操作：", reply_markup=InlineKeyboardMarkup(keyboard))

    elif forward_origin and forward_origin.type.name == "HIDDEN_USER":
        sender_name = getattr(forward_origin, "sender_user_name", "未知")
        await message.reply_text(f"⚠️ 原始用户设置了隐私保护。\n昵称为：{sender_name}")
    else:
        await message.reply_text("⚠️ 无法识别原始用户信息。")


    



def build_attribute_keyboard(user_data, target_user_id):
    data = user_data.get(f"attrs_{target_user_id}", {chr(i): 0 for i in range(ord("A"), ord("G"))})

    def button(name):
        icon = "✅" if data.get(name) else "🟥"
        return InlineKeyboardButton(f"{icon} {CONVERT_DATA[name]}", callback_data=f"attr_{name}")

    keyboard = [
        [button("A"), button("B"), button("C")],
        [button("D"), button("E"), button("F")],
        [
            InlineKeyboardButton("✅ 完成", callback_data="submit"),
            InlineKeyboardButton("🔄 重新标记", callback_data="reset")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)



async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    target_user_id = context.user_data.get("target_user_id")
    target_username = context.user_data.get("target_username", "无")

    if not target_user_id:
        await query.edit_message_text(f"宝贝 {query.from_user.first_name}  (用户名 @{query.from_user.username})，不要操作别人的按钮。")
        return



    if query.data.startswith("mark:"):
        _, allowed_user_id_str, target_user_id_str, username = query.data.split(":")
        allowed_user_id = int(allowed_user_id_str)
        target_user_id = int(target_user_id_str)

        if query.from_user.id != allowed_user_id:
            await query.answer("⛔️ 你无权操作这个按钮。", show_alert=True)
            return

        context.user_data[f"attrs_{target_user_id}"] = {chr(i): 0 for i in range(ord("A"), ord("G"))}
        await query.edit_message_text(
            f"请为用户 @{username} 进行标记：",
            reply_markup=build_attribute_keyboard(context.user_data, target_user_id)
        )



    elif query.data == "reset":
        context.user_data[f"attrs_{target_user_id}"] = {chr(i): 0 for i in range(ord("A"), ord("G"))}
        await query.edit_message_text(
            f"请重新为用户 @{target_username} 标记：",
            reply_markup=build_attribute_keyboard(context.user_data, target_user_id)
        )


    elif query.data == "submit":
        data = context.user_data.get(f"attrs_{target_user_id}", {})

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(f"SELECT id FROM {TABLE_NAME} WHERE id=?", (target_user_id,))
        exists = cursor.fetchone()

        if exists:
            for key, value in data.items():
                if value:
                    cursor.execute(f"""
                        UPDATE {TABLE_NAME}
                        SET {key} = COALESCE({key}, 0) + 1
                        WHERE id=?
                    """, (target_user_id,))
        else:
            fields = ["id"] + list(data.keys())
            values = [target_user_id] + [data[k] for k in data]
            placeholders = ", ".join(["?"] * len(values))
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} ({', '.join(fields)})
                VALUES ({placeholders})
            """, values)

        conn.commit()
        cursor.execute(f"SELECT A, B, C, D, E, F FROM {TABLE_NAME} WHERE id=?", (target_user_id,))
        row = cursor.fetchone()
        conn.close()

        marked_display = ", ".join([f"{CONVERT_DATA[k]}" for k, v in data.items() if v])
        # print("标记的属性：", marked_display)
        summary = "\n".join([f"{CONVERT_DATA[chr(65+i)]} X {value}" for i, value in enumerate(row)])

        await query.edit_message_text(
            f"✅ 已成功标记用户 @{target_username}（ID: {target_user_id}）\n\n"
            f"📍 本次标记：{marked_display}\n\n"
            f"📊 当前累计数据：\n{summary}"
        )

    elif query.data.startswith("attr_"):
        attr = query.data.split("_")[1]
        attrs_key = f"attrs_{target_user_id}"
        if attrs_key not in context.user_data:
            context.user_data[attrs_key] = {chr(i): 0 for i in range(ord("A"), ord("G"))}

        context.user_data[attrs_key][attr] = 1 - context.user_data[attrs_key].get(attr, 0)
        await query.edit_message_reply_markup(reply_markup=build_attribute_keyboard(context.user_data, target_user_id))

    elif query.data.startswith("manual_mark:"):
        target_user_id = int(query.data.split(":")[1])
        context.user_data["target_user_id"] = target_user_id
        context.user_data["target_username"] = "无"  # 手动输入 ID 没有用户名

        context.user_data[f"attrs_{target_user_id}"] = {chr(i): 0 for i in range(ord("A"), ord("G"))}

        await query.edit_message_text(
            f"请为用户 ID {target_user_id} 进行标记：",
            reply_markup=build_attribute_keyboard(context.user_data, target_user_id)
        )




# 初始化应用
YOUR_TELEGRAM_BOT_TOKEN = "7525356538:AAFfnKri-z-FVtf6PKmh5bf3jprdsA8xwdI"  # 用你的真实 Token 替换
app = ApplicationBuilder().token(YOUR_TELEGRAM_BOT_TOKEN).build()

# 添加处理器
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.GROUPS, handle_forward))
app.add_handler(CallbackQueryHandler(button_handler))

from telegram.ext import MessageHandler, filters, CommandHandler, CallbackQueryHandler

# ConversationHandler for "标记" 关键词触发
manual_mark_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & filters.Regex(r"^\s*手动标记\s*$"), trigger_manual_mark)],
    states={
        WAITING_FOR_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_id_input)],
    },
    fallbacks=[],
)

app.add_handler(manual_mark_handler)


# 启动轮询
app.run_polling()
