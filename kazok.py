import asyncio
import logging
import sqlite3
import random
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, PreCheckoutQuery, LabeledPrice
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ================= НАСТРОЙКИ =================
TOKEN = "9016571519:AAFCZWY0pfgZU-x2JXzm2B62hQP2gJ_EWmM" 
ADMIN_IDS = [8624408698, 7088402556]  
CHANNEL_ID = -1002170802203  
BANNER_URL = "https://imgur.com/zScJ9eX"
LOTTERY_PHOTO = "https://imgur.com/zScJ9eX"  # Прямая ссылка на баннер
# ==================================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ================= СОСТОЯНИЯ =================
class AdminState(StatesGroup):
    waiting_prize = State()
    waiting_price = State()
    waiting_max_tickets = State()

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect("lottery.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prize_name TEXT,
    ticket_price INTEGER,
    max_tickets INTEGER,
    status TEXT DEFAULT 'active',
    winner_id INTEGER,
    msg_id INTEGER
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER,
    user_id INTEGER,
    username TEXT,
    amount INTEGER DEFAULT 1
)""")
conn.commit()

# ================= КЛАВИАТУРЫ =================
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Наш канал", url="https://t.me/sugarlolypop")], 
        [InlineKeyboardButton(text="👑 Админ-панель", callback_data="open_admin")]
    ])

def kb_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Создать новый слот", callback_data="create_slot")]
    ])

def kb_channel(slot_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 Купить билет", callback_data=f"buy_ticket_{slot_id}")]
    ])

# ================= СТАРТ (С БАННЕРОМ) =================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        f"🎰 <b>Добро пожаловать в Бот Розыгрышей, {message.from_user.first_name}!</b>\n\n"
        "Здесь проходят конкурсы и розыгрыши призов.\n"
        "Заходи в наш канал, чтобы участвовать!\n\n"
        "👇 Если ты админ, нажми кнопку ниже:"
    )
    
    try:
        await message.answer_photo(
            photo=LOTTERY_PHOTO,
            caption=text,
            reply_markup=kb_main()
        )
    except Exception:
        await message.answer(text, reply_markup=kb_main())

@dp.callback_query(F.data == "open_admin")
async def open_admin(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("У вас нет доступа!", show_alert=True)
        return
    await cb.message.edit_text("👑 <b>Админ-панель лотереи</b>\nСоздайте слот:", reply_markup=kb_admin())

# ================= АДМИН-ПАНЕЛЬ =================
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await message.answer("👑 <b>Админ-панель лотереи</b>\nСоздайте слот:", reply_markup=kb_admin())

@dp.callback_query(F.data == "create_slot")
async def create_slot(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await cb.message.edit_text("Введите название приза (на что конкурс):")
    await state.set_state(AdminState.waiting_prize)

@dp.message(AdminState.waiting_prize)
async def process_prize(message: Message, state: FSMContext):
    await state.update_data(prize=message.text)
    await message.answer("Введите цену одного билета в ЗВЕЗДАХ (например: 50):")
    await state.set_state(AdminState.waiting_price)

@dp.message(AdminState.waiting_price)
async def process_price(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    await state.update_data(price=int(message.text))
    await message.answer("Введите ОБЩЕЕ количество билетов (например: 10):")
    await state.set_state(AdminState.waiting_max_tickets)

@dp.message(AdminState.waiting_max_tickets)
async def process_max(message: Message, state: FSMContext):
    if not message.text.isdigit(): 
        return await message.answer("Введите число!")
    
    max_t = int(message.text)
    data = await state.get_data()
    
    cursor.execute("INSERT INTO slots (prize_name, ticket_price, max_tickets) VALUES (?, ?, ?)",
                   (data['prize'], data['price'], max_t))
    slot_id = cursor.lastrowid
    conn.commit()
    
    text = (
        f"🎉 <b>НОВЫЙ РОЗЫГРЫШ!</b> 🎉\n\n"
        f"🎁 <b>Приз:</b> {data['prize']}\n"
        f"🎟 <b>Цена билета:</b> {data['price']} ⭐\n"
        f"🔢 <b>Всего билетов:</b> {max_t}\n"
        f"📊 <b>Куплено:</b> 0 / {max_t}\n\n"
        f"👇 Жми кнопку ниже, чтобы испытать удачу!"
    )
    
    try:
        msg = await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=LOTTERY_PHOTO,
            caption=text,
            reply_markup=kb_channel(slot_id)
        )
        cursor.execute("UPDATE slots SET msg_id = ? WHERE id = ?", (msg.message_id, slot_id))
        conn.commit()
        await message.answer(f"✅ Слот создан и отправлен в канал!")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки в канал: {e}")
        
    await state.clear()

# ================= ПОКУПКА БИЛЕТА (ИСПРАВЛЕНО ОТ СПАМА) =================
@dp.callback_query(F.data.startswith("buy_ticket_"))
async def buy_ticket(cb: CallbackQuery):
    slot_id = int(cb.data.split("_")[2])
    slot = cursor.execute("SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()
    
    if not slot or slot['status'] != 'active':
        await cb.answer("❌ Розыгрыш завершен!", show_alert=True)
        return
        
    tickets_bought = cursor.execute("SELECT SUM(amount) FROM tickets WHERE slot_id = ?", (slot_id,)).fetchone()[0] or 0
    if tickets_bought >= slot['max_tickets']:
        await cb.answer("❌ Билеты закончились!", show_alert=True)
        return

    # Отправляем счет В ЛИЧКУ
    await bot.send_message(
        chat_id=cb.from_user.id,
        text=f"🎟 Вы покупаете билет на розыгрыш:\n<b>{slot['prize_name']}</b>\n\nЦена: <b>{slot['ticket_price']} ⭐</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Оплатить {slot['ticket_price']} ⭐", callback_data=f"pay_ticket_{slot_id}")]
        ])
    )
    await cb.answer("Счет отправлен вам в личные сообщения!", show_alert=True)

@dp.callback_query(F.data.startswith("pay_ticket_"))
async def pay_ticket(cb: CallbackQuery):
    slot_id = int(cb.data.split("_")[2])
    slot = cursor.execute("SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()
    
    await cb.message.answer_invoice(
        title=f"Билет: {slot['prize_name']}",
        description="Участие в розыгрыше",
        payload=f"ticket_{slot_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Билет", amount=slot['ticket_price'])]
    )
    await cb.answer()

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    if not payload.startswith("ticket_"): return
    
    slot_id = int(payload.replace("ticket_", ""))
    uid = message.from_user.id
    username = message.from_user.username or "Скрыт"
    
    slot = cursor.execute("SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()
    if not slot or slot['status'] != 'active': return

    # Записываем билет (если уже покупал - добавляем к количеству)
    existing = cursor.execute("SELECT id, amount FROM tickets WHERE slot_id = ? AND user_id = ?", (slot_id, uid)).fetchone()
    if existing:
        cursor.execute("UPDATE tickets SET amount = amount + 1 WHERE id = ?", (existing['id'],))
    else:
        cursor.execute("INSERT INTO tickets (slot_id, user_id, username, amount) VALUES (?, ?, ?, 1)", (slot_id, uid, username))
    conn.commit()
    
    tickets_bought = cursor.execute("SELECT SUM(amount) FROM tickets WHERE slot_id = ?", (slot_id,)).fetchone()[0] or 0
    remaining = slot['max_tickets'] - tickets_bought
    
    await message.answer(f"✅ <b>Билет куплен!</b>\n\nОсталось билетов: <b>{remaining}</b>\nЖдите результатов!")
    
    # Обновляем пост в канале (добавляем участника и счетчик)
    await update_channel_post(slot_id)
    
    # Если купили все - розыгрыш
    if tickets_bought >= slot['max_tickets']:
        await draw_winner(slot_id)

# ================= ОБНОВЛЕНИЕ ПОСТА (СПИСОК УЧАСТНИКОВ) =================
async def update_channel_post(slot_id):
    slot = cursor.execute("SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()
    tickets_bought = cursor.execute("SELECT SUM(amount) FROM tickets WHERE slot_id = ?", (slot_id,)).fetchone()[0] or 0
    
    participants = cursor.execute("SELECT username, amount FROM tickets WHERE slot_id = ? ORDER BY amount DESC", (slot_id,)).fetchall()
    
    text = (
        f"🎉 <b>РОЗЫГРЫШ!</b> 🎉\n\n"
        f"🎁 Приз: <b>{slot['prize_name']}</b>\n"
        f"🎟 Цена билета: <b>{slot['ticket_price']} ⭐</b>\n"
        f"📊 Куплено билетов: <b>{tickets_bought} / {slot['max_tickets']}</b>\n\n"
    )
    
    if participants:
        text += "👥 <b>Участники:</b>\n"
        for p in participants:
            text += f"• @{p['username']} — {p['amount']} шт.\n"
    else:
        text += "Пока нет участников. Будьте первым!"
        
    try:
        # Обновляем подпись под картинкой
        await bot.edit_message_caption(
            chat_id=CHANNEL_ID,
            message_id=slot['msg_id'],
            caption=text,
            reply_markup=kb_channel(slot_id)
        )
    except Exception:
        pass

# ================= РОЗЫГРЫШ =================
async def draw_winner(slot_id):
    slot = cursor.execute("SELECT * FROM slots WHERE id = ?", (slot_id,)).fetchone()
    
    participants_rows = cursor.execute("SELECT user_id, amount FROM tickets WHERE slot_id = ?", (slot_id,)).fetchall()
    pool = []
    for row in participants_rows:
        pool.extend([row['user_id']] * row['amount']) # У кого 3 билета - тот в списке 3 раза
    
    if not pool: return
    
    winner_id = random.choice(pool)
    
    cursor.execute("UPDATE slots SET status = 'finished', winner_id = ? WHERE id = ?", (winner_id, slot_id))
    conn.commit()
    
    try:
        winner_user = await bot.get_chat(winner_id)
        winner_name = winner_user.first_name
        
        text = (
            f"🏆 <b>РОЗЫГРЫШ ЗАВЕРШЕН!</b>\n\n"
            f"🎁 Приз: {slot['prize_name']}\n"
            f"🥳 Победитель: <a href='tg://user?id={winner_id}'>{winner_name}</a>!\n\n"
            f"Свяжитесь с администратором для получения приза."
        )
        await bot.send_message(CHANNEL_ID, text)
        await bot.send_message(winner_id, f"🥳 <b>Поздравляем! Вы выиграли: {slot['prize_name']}!</b>\nНапишите администратору.")
    except Exception as e:
        logging.error(f"Ошибка при объявлении победителя: {e}")

# ================= ЗАПУСК =================
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())