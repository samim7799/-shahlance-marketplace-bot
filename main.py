import os, sqlite3, asyncio
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CURRENCY = os.getenv("CURRENCY", "USD")
SUPPORT = os.getenv("SUPPORT_USERNAME", "").lstrip("@")
REQUIRED_CHANNEL = "@ShahLance"
REQUIRED_CHANNEL_URL = "https://t.me/ShahLance"
DB = "marketplace.db"

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

bot = Bot(token=TOKEN)
dp = Dispatcher()

def con():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def now():
    return datetime.now(timezone.utc).isoformat()

def dec(x):
    return Decimal(str(x)).quantize(Decimal("0.01"))

def init():
    c = con()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,balance TEXT DEFAULT '0',seller_status TEXT DEFAULT 'none',referred_by INTEGER,referral_earned TEXT DEFAULT '0',created_at TEXT);
    CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,parent_id INTEGER,active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,description TEXT,category_id INTEGER,price TEXT,stock INTEGER DEFAULT 0,seller_id INTEGER,status TEXT DEFAULT 'pending',created_at TEXT);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,buyer_id INTEGER,product_id INTEGER,seller_id INTEGER,qty INTEGER,amount TEXT,status TEXT DEFAULT 'pending',created_at TEXT);
    CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,kind TEXT,amount TEXT,status TEXT,note TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS seller_applications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,details TEXT,status TEXT DEFAULT 'pending',created_at TEXT);
    CREATE TABLE IF NOT EXISTS referrals(id INTEGER PRIMARY KEY AUTOINCREMENT,referrer_id INTEGER,referred_id INTEGER UNIQUE,earned TEXT DEFAULT '0',created_at TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
    """)
    for k, v in [("referral_percent", "5"), ("seller_commission", "10"), ("min_deposit", "5"), ("min_withdraw", "10")]:
        c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
    c.commit()
    c.close()

def register(u, ref=None):
    c = con()
    old = c.execute("SELECT id FROM users WHERE id=?", (u.id,)).fetchone()
    if not old:
        rid = None
        if ref and ref.isdigit() and int(ref) != u.id and c.execute("SELECT id FROM users WHERE id=?", (int(ref),)).fetchone():
            rid = int(ref)
        c.execute("INSERT INTO users(id,username,first_name,referred_by,created_at) VALUES(?,?,?,?,?)", (u.id, u.username, u.first_name, rid, now()))
        if rid:
            c.execute("INSERT OR IGNORE INTO referrals(referrer_id,referred_id,created_at) VALUES(?,?,?)", (rid, u.id, now()))
    else:
        c.execute("UPDATE users SET username=?,first_name=? WHERE id=?", (u.username, u.first_name, u.id))
    c.commit()
    c.close()

def K(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in r] for r in rows])

def main_menu():
    return K([
      [("👤 My Profile", "profile"), ("🛍 Marketplace", "market")],
      [("📦 My Orders", "orders"), ("💰 Wallet", "wallet")],
      [("🏪 Become A Seller", "seller"), ("💬 Support", "support")],
      [("🎁 Referral Program", "referral"), ("📜 Terms And Rules", "terms")]
    ])

LANGS = {
    "en": ("🇬🇧 English", "Welcome to the marketplace.\n\nChoose an option:"),
    "zh": ("🇨🇳 中文", "欢迎来到市场。\n\n请选择一个选项："),
    "ru": ("🇷🇺 Русский", "Добро пожаловать на маркетплейс.\n\nВыберите действие:"),
}

def language_kb():
    return K([
      [("🇬🇧 English", "lang:en")],
      [("🇨🇳 中文", "lang:zh")],
      [("🇷🇺 Русский", "lang:ru")]
    ])

def join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="📢 Join Channel", url=REQUIRED_CHANNEL_URL)],
      [InlineKeyboardButton(text="✅ Check Join", callback_data="check_join")]
    ])

async def is_member(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

@dp.message(CommandStart())
async def start(m: Message):
    parts = m.text.split(maxsplit=1)
    register(m.from_user, parts[1][4:] if len(parts) > 1 and parts[1].startswith("ref_") else None)
    await m.answer("🌐 Please select your language / ভাষা নির্বাচন করুন:", reply_markup=language_kb())

@dp.callback_query(F.data.startswith("lang:"))
async def choose_language(q: CallbackQuery):
    lang = q.data.split(":")[1]
    await q.message.edit_text(
        f"✅ Language selected: {LANGS[lang][0]}\n\n- ✅ Start Using ✅ -",
        reply_markup=K([[("🚀 Start Using", "start_using")]])
    )
    await q.answer()

@dp.callback_query(F.data == "start_using")
async def start_using(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text(
            "👋 Hello!\n\n🔒 You must join our channel below to use this bot:",
            reply_markup=join_kb()
        )
        return await q.answer("Please join the channel first.", show_alert=True)
    await q.message.edit_text("🏠 Welcome to the marketplace.\n\nChoose an option:", reply_markup=main_menu())
    await q.answer()

@dp.callback_query(F.data == "check_join")
async def check_join(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.answer("❌ You have not joined the channel yet.", show_alert=True)
        return
    await q.message.edit_text("✅ Membership verified.\n\n🏠 Welcome to the marketplace.", reply_markup=main_menu())
    await q.answer()

@dp.callback_query(F.data == "profile")
async def profile(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    c = con()
    u = c.execute("SELECT * FROM users WHERE id=?", (q.from_user.id,)).fetchone()
    n = c.execute("SELECT COUNT(*) n FROM orders WHERE buyer_id=?", (q.from_user.id,)).fetchone()["n"]
    c.close()
    await q.message.edit_text(
        f"👤 My Profile\n\n🆔 ID: {u['id']}\n👤 @{u['username'] or 'N/A'}\n💰 Balance: {u['balance']} {CURRENCY}\n📦 Orders: {n}\n🏪 Seller status: {u['seller_status']}",
        reply_markup=K([[("💰 Wallet", "wallet"), ("📦 Orders", "orders")], [("⬅️ Main Menu", "home")]])
    )
    await q.answer()

@dp.callback_query(F.data == "market")
async def market(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    c = con()
    rows = c.execute("SELECT * FROM categories WHERE active=1 AND parent_id IS NULL ORDER BY id").fetchall()
    c.close()
    buttons = [[(r["name"], f"cat:{r['id']}")] for r in rows] or [[("No categories yet", "noop")]]
    buttons.append([("⬅️ Main Menu", "home")])
    await q.message.edit_text("🛍 Marketplace\n\nSelect a category:", reply_markup=K(buttons))
    await q.answer()

@dp.callback_query(F.data.startswith("cat:"))
async def cat(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    cid = int(q.data.split(":")[1])
    c = con()
    subs = c.execute("SELECT * FROM categories WHERE parent_id=? AND active=1", (cid,)).fetchall()
    ps = c.execute("SELECT * FROM products WHERE category_id=? AND status='approved' ORDER BY id DESC LIMIT 20", (cid,)).fetchall()
    c.close()
    b = [[(s["name"], f"cat:{s['id']}")] for s in subs]
    b += [[(f"🛒 {p['name']} — {p['price']} {CURRENCY}", f"prod:{p['id']}")] for p in ps]
    b.append([("⬅️ Back", "market")])
    await q.message.edit_text("Select a subcategory or product:", reply_markup=K(b or [[("No products available", "noop")], [("⬅️ Back", "market")]]))
    await q.answer()

@dp.callback_query(F.data.startswith("prod:"))
async def prod(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    pid = int(q.data.split(":")[1])
    c = con()
    p = c.execute("SELECT * FROM products WHERE id=? AND status='approved'", (pid,)).fetchone()
    c.close()
    if not p:
        return await q.answer("Product unavailable", show_alert=True)
    await q.message.edit_text(
        f"🛍 {p['name']}\n\n{p['description'] or 'No description'}\n\n💵 {p['price']} {CURRENCY}\n📦 Stock: {p['stock']}",
        reply_markup=K([[("🛒 Buy Now", f"buy:{pid}")], [("⬅️ Back", "market")]])
    )
    await q.answer()

@dp.callback_query(F.data.startswith("buy:"))
async def buy(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    pid = int(q.data.split(":")[1])
    c = con()
    p = c.execute("SELECT * FROM products WHERE id=? AND status='approved'", (pid,)).fetchone()
    u = c.execute("SELECT * FROM users WHERE id=?", (q.from_user.id,)).fetchone()
    if not p or p["stock"] < 1:
        c.close()
        return await q.answer("Out of stock", show_alert=True)
    price = dec(p["price"])
    if dec(u["balance"]) < price:
        c.close()
        return await q.answer("Insufficient balance", show_alert=True)
    c.execute("BEGIN IMMEDIATE")
    c.execute("UPDATE users SET balance=? WHERE id=?", (str(dec(u["balance"]) - price), u["id"]))
    c.execute("UPDATE products SET stock=stock-1 WHERE id=? AND stock>0", (pid,))
    cur = c.execute("INSERT INTO orders(buyer_id,product_id,seller_id,qty,amount,status,created_at) VALUES(?,?,?,?,?,?,?)", (u["id"], pid, p["seller_id"], 1, str(price), "pending", now()))
    oid = cur.lastrowid
    c.execute("INSERT INTO transactions(user_id,kind,amount,status,note,created_at) VALUES(?,?,?,?,?,?)", (u["id"], "purchase", str(price), "completed", f"Order #{oid}", now()))
    c.commit()
    c.close()
    await q.message.edit_text(
        f"✅ Order created\n\nOrder ID: #{oid}\nAmount: {price} {CURRENCY}\nStatus: Pending",
        reply_markup=K([[("📦 My Orders", "orders"), ("🛍 Marketplace", "market")], [("⬅️ Main Menu", "home")]])
    )
    await q.answer()

@dp.callback_query(F.data == "orders")
async def orders(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    c = con()
    rs = c.execute("SELECT o.id,o.amount,o.status,p.name FROM orders o JOIN products p ON p.id=o.product_id WHERE o.buyer_id=? ORDER BY o.id DESC LIMIT 20", (q.from_user.id,)).fetchall()
    c.close()
    text = "📦 My Orders\n\n" + ("\n".join(f"#{r['id']} • {r['name']} • {r['amount']} {CURRENCY} • {r['status']}" for r in rs) if rs else "No orders yet.")
    await q.message.edit_text(text, reply_markup=K([[("🛍 Marketplace", "market")], [("⬅️ Main Menu", "home")]]))
    await q.answer()

@dp.callback_query(F.data == "wallet")
async def wallet(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    c = con()
    u = c.execute("SELECT balance FROM users WHERE id=?", (q.from_user.id,)).fetchone()
    c.close()
    await q.message.edit_text(f"💰 Wallet\n\nBalance: {u['balance']} {CURRENCY}\n\n➕ Deposit: /deposit AMOUNT\n💸 Withdraw: /withdraw AMOUNT PAYMENT_DETAILS", reply_markup=K([[("⬅️ Main Menu", "home")]]))
    await q.answer()

@dp.message(Command("deposit"))
async def deposit(m: Message):
    register(m.from_user)
    p = m.text.split()
    if len(p) != 2:
        return await m.answer("Usage: /deposit 25")
    try:
        a = dec(p[1])
    except:
        return await m.answer("Invalid amount")
    c = con()
    cur = c.execute("INSERT INTO transactions(user_id,kind,amount,status,note,created_at) VALUES(?,?,?,?,?,?)", (m.from_user.id, "deposit", str(a), "pending", "Manual deposit request", now()))
    tid = cur.lastrowid
    c.commit()
    c.close()
    await m.answer(f"⏳ Deposit request #{tid} submitted for {a} {CURRENCY}.")
    if ADMIN_ID:
        await bot.send_message(chat_id=ADMIN_ID, text=f"💰 Deposit #{tid}\nUser: {m.from_user.id}\nAmount: {a}\n/approve_deposit {tid}")

@dp.message(Command("withdraw"))
async def withdraw(m: Message):
    register(m.from_user)
    p = m.text.split(maxsplit=2)
    if len(p) < 3:
        return await m.answer("Usage: /withdraw 25 PAYMENT_DETAILS")
    try:
        a = dec(p[1])
    except:
        return await m.answer("Invalid amount")
    c = con()
    u = c.execute("SELECT balance FROM users WHERE id=?", (m.from_user.id,)).fetchone()
    if dec(u["balance"]) < a:
        c.close()
        return await m.answer("Insufficient balance")
    c.execute("UPDATE users SET balance=? WHERE id=?", (str(dec(u["balance"]) - a), m.from_user.id))
    cur = c.execute("INSERT INTO transactions(user_id,kind,amount,status,note,created_at) VALUES(?,?,?,?,?,?)", (m.from_user.id, "withdrawal", str(a), "pending", p[2], now()))
    tid = cur.lastrowid
    c.commit()
    c.close()
    await m.answer(f"⏳ Withdrawal #{tid} submitted.")
    if ADMIN_ID:
        await bot.send_message(chat_id=ADMIN_ID, text=f"💸 Withdrawal #{tid}\nUser: {m.from_user.id}\nAmount: {a}\nDetails: {p[2]}\n/approve_withdraw {tid}\n/reject_withdraw {tid}")

@dp.callback_query(F.data == "seller")
async def seller(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    c = con()
    u = c.execute("SELECT seller_status FROM users WHERE id=?", (q.from_user.id,)).fetchone()
    c.close()
    if u["seller_status"] == "approved":
        return await q.message.edit_text("🏪 Seller Center", reply_markup=K([[("➕ Add Product", "seller_add"), ("📦 My Products", "seller_products")], [("📊 Sales", "seller_sales")], [("⬅️ Main Menu", "home")]]))
    await q.message.edit_text("🏪 Become A Seller\n\nApply with /seller_apply followed by what you sell and your experience.\n\nOnly lawful, authorized and platform-compliant products/services are allowed.", reply_markup=K([[("📜 Seller Rules", "terms")], [("⬅️ Main Menu", "home")]]))
    await q.answer()

@dp.message(Command("seller_apply"))
async def seller_apply(m: Message):
    register(m.from_user)
    d = m.text.partition(" ")[2].strip()
    if not d:
        return await m.answer("Usage: /seller_apply What you sell + experience")
    c = con()
    c.execute("INSERT INTO seller_applications(user_id,details,created_at) VALUES(?,?,?)", (m.from_user.id, d, now()))
    c.execute("UPDATE users SET seller_status='pending' WHERE id=?", (m.from_user.id,))
    c.commit()
    c.close()
    await m.answer("⏳ Seller application submitted for review.")
    if ADMIN_ID:
        await bot.send_message(chat_id=ADMIN_ID, text=f"🏪 Seller application\nUser: {m.from_user.id}\n{d}\n/approve_seller {m.from_user.id}")

@dp.callback_query(F.data == "referral")
async def referral(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    c = con()
    u = c.execute("SELECT referral_earned FROM users WHERE id=?", (q.from_user.id,)).fetchone()
    n = c.execute("SELECT COUNT(*) n FROM referrals WHERE referrer_id=?", (q.from_user.id,)).fetchone()["n"]
    c.close()
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{q.from_user.id}"
    await q.message.edit_text(f"🎁 Referral Program\n\n👥 Referrals: {n}\n💰 Earned: {u['referral_earned']} {CURRENCY}\n\n🔗 {link}\n\nRate: 5% (admin configurable)", reply_markup=K([[("⬅️ Main Menu", "home")]]))
    await q.answer()

@dp.callback_query(F.data == "support")
async def support(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    markup = K([[("⬅️ Main Menu", "home")]])
    text = "💬 Support\n\nSupport is not configured yet."
    if SUPPORT:
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👨‍💻 Contact Support", url=f"https://t.me/{SUPPORT}")], [InlineKeyboardButton(text="⬅️ Main Menu", callback_data="home")]])
        text = f"💬 Support\n\nContact @{SUPPORT}"
    await q.message.edit_text(text, reply_markup=markup)
    await q.answer()

@dp.callback_query(F.data == "terms")
async def terms(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    await q.message.edit_text("📜 Terms And Rules\n\nOnly lawful, authorized and platform-compliant products/services may be listed. Fraud, stolen/compromised accounts, spam, abuse and prohibited goods/services are not allowed. Orders can be reviewed or cancelled for policy violations.", reply_markup=K([[("⬅️ Main Menu", "home")]]))
    await q.answer()

@dp.callback_query(F.data == "home")
async def home(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text("🔒 Please join our required channel first.", reply_markup=join_kb())
        return await q.answer("Join the channel first.", show_alert=True)
    await q.message.edit_text("🏠 Main Menu", reply_markup=main_menu())
    await q.answer()

@dp.callback_query(F.data == "noop")
async def noop(q: CallbackQuery):
    await q.answer()

@dp.message(Command("approve_deposit"))
async def ad(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    p = m.text.split()
    c = con()
    if len(p) != 2:
        return await m.answer("Usage: /approve_deposit TX_ID")
    tx = c.execute("SELECT * FROM transactions WHERE id=? AND kind='deposit' AND status='pending'", (int(p[1]),)).fetchone()
    if not tx:
        c.close()
        return await m.answer("Not found")
    u = c.execute("SELECT balance FROM users WHERE id=?", (tx["user_id"],)).fetchone()
    c.execute("UPDATE users SET balance=? WHERE id=?", (str(dec(u["balance"]) + dec(tx["amount"])), tx["user_id"]))
    c.execute("UPDATE transactions SET status='completed' WHERE id=?", (tx["id"],))
    c.commit()
    c.close()
    await m.answer("Deposit approved")
    await bot.send_message(chat_id=tx["user_id"], text=f"✅ Deposit approved: {tx['amount']} {CURRENCY}")

@dp.message(Command("approve_withdraw"))
async def aw(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    p = m.text.split()
    c = con()
    tx = c.execute("SELECT * FROM transactions WHERE id=? AND kind='withdrawal' AND status='pending'", (int(p[1]),)).fetchone() if len(p) == 2 else None
    if not tx:
        c.close()
        return await m.answer("Not found")
    c.execute("UPDATE transactions SET status='completed' WHERE id=?", (tx["id"],))
    c.commit()
    c.close()
    await m.answer("Withdrawal approved")
    await bot.send_message(chat_id=tx["user_id"], text=f"✅ Withdrawal approved: {tx['amount']} {CURRENCY}")

@dp.message(Command("reject_withdraw"))
async def rw(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    p = m.text.split()
    c = con()
    tx = c.execute("SELECT * FROM transactions WHERE id=? AND kind='withdrawal' AND status='pending'", (int(p[1]),)).fetchone() if len(p) == 2 else None
    if not tx:
        c.close()
        return await m.answer("Not found")
    u = c.execute("SELECT balance FROM users WHERE id=?", (tx["user_id"],)).fetchone()
    c.execute("UPDATE users SET balance=? WHERE id=?", (str(dec(u["balance"]) + dec(tx["amount"])), tx["user_id"]))
    c.execute("UPDATE transactions SET status='rejected' WHERE id=?", (tx["id"],))
    c.commit()
    c.close()
    await m.answer("Rejected and returned")
    await bot.send_message(chat_id=tx["user_id"], text=f"❌ Withdrawal rejected; {tx['amount']} returned.")

@dp.message(Command("approve_seller"))
async def aseller(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    p = m.text.split()
    if len(p) != 2:
        return await m.answer("Usage: /approve_seller USER_ID")
    c = con()
    c.execute("UPDATE users SET seller_status='approved' WHERE id=?", (int(p[1]),))
    c.commit()
    c.close()
    await m.answer("Seller approved")
    await bot.send_message(chat_id=int(p[1]), text="✅ Seller application approved.")

@dp.message(Command("seed"))
async def seed(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    c = con()
    cats = [("👤 Accounts", None), ("📱 SMM Services", None), ("💻 Software & Licenses", None), ("🎮 Gaming", None), ("🌐 Hosting", None), ("🛠 Custom Services", None)]
    for name, parent in cats:
        c.execute("INSERT INTO categories(name,parent_id) SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM categories WHERE name=? AND parent_id IS ?)", (name, parent, name, parent))
    pairs = [
        ("👤 Accounts", ["📱 Social Accounts", "💘 Dating Accounts", "₿ Crypto-related Accounts", "🎮 Gaming Accounts", "📧 Email Accounts"]),
        ("📱 SMM Services", ["👥 Followers", "❤️ Likes", "💬 Comments", "👁 Views", "🔄 Shares", "📸 Instagram", "🎵 TikTok", "▶️ YouTube", "📱 Telegram"])
    ]
    for parent, subs in pairs:
        r = c.execute("SELECT id FROM categories WHERE name=? AND parent_id IS NULL", (parent,)).fetchone()
        for s in subs:
            if r:
                c.execute("INSERT INTO categories(name,parent_id) SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM categories WHERE name=? AND parent_id=?)", (s, r["id"], s, r["id"]))
    c.commit()
    c.close()
    await m.answer("✅ Starter categories created.")

async def main():
    init()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
