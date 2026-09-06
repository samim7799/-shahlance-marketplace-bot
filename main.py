import os
import sqlite3
import asyncio
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
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


WELCOME_TEXT = (
    "ShahLance Digital Marketplace \n\n"
    "A premium and trusted platform for buying and selling digital goods with confidence, security, and Reliable transactions. 🛒 \n\n"
    "Why Choose & Trust Us ? \n\n"
    "💎Premium Product & Service\n"
    "🌐20+ Categories  Available \n"
    "⭐Trusted  Sellers & Quality\n"
    "🛡️Safe & Reliable Purchase \n"
    " 🖇️100%  Escrow  Protection \n"
    "🔒Secure  & Verified  Deals\n"
    "⚡Instant  & Fast  Delivery\n"
    "✅Verified  &  Safe  Sellers\n"
    "🧑🏼‍💻24/7 Live OnlineSupport"
)


MARKET_TEXT = (
    "🧑🏼‍💻ShahLance Digital Marketplace 🛒\n\n"
    "Explore our premium, verified digital products and services below. "
    "Select your preferred category to view available items and place your order securely.\n\n"
    "💎 Why Buy With Us?\n\n"
    "• Fast & Reliable Delivery: Get your items instantly or within a short processing time.\n\n"
    "• 100% Secure Escrow: Your funds are fully protected until the order is successfully fulfilled.\n\n"
    "• Trusted Quality: All listed services and products are strictly verified.\n\n"
    "👇 Select a category below to browse items :"
)


def con():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def now():
    return datetime.now(timezone.utc).isoformat()


def dec(x):
    return Decimal(str(x)).quantize(Decimal("0.01"))


def init():
    c = con()

    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance TEXT DEFAULT '0',
            seller_status TEXT DEFAULT 'none',
            referred_by INTEGER,
            referral_earned TEXT DEFAULT '0',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            parent_id INTEGER,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            category_id INTEGER,
            price TEXT,
            stock INTEGER DEFAULT 0,
            seller_id INTEGER,
            status TEXT DEFAULT 'pending',
            sold_count INTEGER DEFAULT 0,
            rating REAL DEFAULT 5.0,
            reviews_count INTEGER DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER,
            product_id INTEGER,
            seller_id INTEGER,
            qty INTEGER,
            amount TEXT,
            status TEXT DEFAULT 'escrow_pending',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT,
            amount TEXT,
            status TEXT,
            note TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS seller_applications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            details TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS reviews(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            buyer_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS favorites(
            user_id INTEGER,
            product_id INTEGER,
            PRIMARY KEY(user_id, product_id)
        );

        CREATE TABLE IF NOT EXISTS referrals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER UNIQUE,
            earned TEXT DEFAULT '0',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )

    for k, v in [
        ("referral_percent", "5"),
        ("seller_commission", "10"),
        ("min_deposit", "5"),
        ("min_withdraw", "10"),
    ]:
        c.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (k, v),
        )

    c.commit()
    c.close()


def register(u, ref=None):
    c = con()

    old = c.execute(
        "SELECT id FROM users WHERE id=?",
        (u.id,),
    ).fetchone()

    if not old:
        rid = None

        if (
            ref
            and ref.isdigit()
            and int(ref) != u.id
            and c.execute(
                "SELECT id FROM users WHERE id=?",
                (int(ref),),
            ).fetchone()
        ):
            rid = int(ref)

        c.execute(
            """
            INSERT INTO users(
                id,
                username,
                first_name,
                referred_by,
                created_at
            )
            VALUES(?,?,?,?,?)
            """,
            (
                u.id,
                u.username,
                u.first_name,
                rid,
                now(),
            ),
        )

        if rid:
            c.execute(
                """
                INSERT OR IGNORE INTO referrals(
                    referrer_id,
                    referred_id,
                    earned,
                    created_at
                )
                VALUES(?,?,?,?)
                """,
                (
                    rid,
                    u.id,
                    "0",
                    now(),
                ),
            )

    else:
        c.execute(
            """
            UPDATE users
            SET username=?, first_name=?
            WHERE id=?
            """,
            (
                u.username,
                u.first_name,
                u.id,
            ),
        )

    c.commit()
    c.close()


def K(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t,
                    callback_data=d,
                )
                for t, d in r
            ]
            for r in rows
        ]
    )


def main_menu():
    return K(
        [
            [("👤 My Profile", "profile"), ("🛍️ Marketplace", "market")],
            [("📦 My Orders", "orders"), ("💰 My Wallet", "wallet")],
            [("🤝 Become A Seller", "seller"), ("👨‍💻 Admin Support", "support")],
            [("🎁 Referral Program", "referral"), ("📜 Terms And Rules", "terms")],
        ]
    )


LANGS = {
    "en": (
        "🇬🇧 English",
        "Welcome to the marketplace.\n\nChoose an option:",
    ),
}


def language_kb():
    return K([[("🇬🇧 English", "lang:en")]])


def join_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Join Channel",
                    url=REQUIRED_CHANNEL_URL,
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Check Join",
                    callback_data="check_join",
                )
            ],
        ]
    )


async def is_member(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL,
            user_id=user_id,
        )

        return member.status in (
            "member",
            "administrator",
            "creator",
        )

    except Exception:
        return False


@dp.message(CommandStart())
async def start(m: Message):
    parts = (m.text or "").split(maxsplit=1)

    ref = None

    if len(parts) > 1 and parts[1].startswith("ref_"):
        ref = parts[1][4:]

    register(m.from_user, ref)

    await m.answer(
        "🌐 Please select your language:",
        reply_markup=language_kb(),
    )


@dp.callback_query(F.data.startswith("lang:"))
async def choose_language(q: CallbackQuery):
    await q.message.edit_text(
        "✅ Language selected!\n\n- ✅ Start Using ✅ -",
        reply_markup=K(
            [[("🚀 Start Using", "start_using")]]
        ),
    )

    await q.answer()


@dp.callback_query(F.data == "start_using")
async def start_using(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text(
            "👋 Hello!\n\n"
            "🔒 You must join our channel below to use this bot:",
            reply_markup=join_kb(),
        )

        return await q.answer(
            "Please join the channel first.",
            show_alert=True,
        )

    await q.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu(),
    )

    await q.answer()


@dp.callback_query(F.data == "check_join")
async def check_join(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        return await q.answer(
            "❌ You have not joined the channel yet.",
            show_alert=True,
        )

    await q.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu(),
    )

    await q.answer()


@dp.callback_query(F.data == "profile")
async def profile(q: CallbackQuery):
    c = con()

    u = c.execute(
        "SELECT * FROM users WHERE id=?",
        (q.from_user.id,),
    ).fetchone()

    n = c.execute(
        "SELECT COUNT(*) n FROM orders WHERE buyer_id=?",
        (q.from_user.id,),
    ).fetchone()["n"]

    c.close()

    if not u:
        register(q.from_user)

        c = con()

        u = c.execute(
            "SELECT * FROM users WHERE id=?",
            (q.from_user.id,),
        ).fetchone()

        c.close()

    await q.message.edit_text(
        f"👤 My Profile\n\n"
        f"🆔 ID: {u['id']}\n"
        f"👤 @{u['username'] or 'N/A'}\n"
        f"💰 Balance: {u['balance']} {CURRENCY}\n"
        f"📦 Orders: {n}\n"
        f"🏪 Seller status: {u['seller_status']}",
        reply_markup=K(
            [
                [("💰 My Wallet", "wallet"), ("📦 Orders", "orders")],
                [("⬅️ Main Menu", "home")],
            ]
        ),
    )

    await q.answer()


@dp.callback_query(F.data == "market")
async def market(q: CallbackQuery):
    if not await is_member(q.from_user.id):
        await q.message.edit_text(
            "🔒 Please join our channel first.",
            reply_markup=join_kb(),
        )

        return await q.answer(
            "Join channel first",
            show_alert=True,
        )

    c = con()

    rows = c.execute(
        """
        SELECT *
        FROM categories
        WHERE active=1
        AND parent_id IS NULL
        ORDER BY id
        """
    ).fetchall()

    c.close()

    buttons = [
        [
            ("🔎 Search", "m_search"),
            ("🔥 Trending", "m_trend"),
            ("⭐ Top Rated", "m_top"),
        ],
        [
            ("🆕 Newest", "m_new"),
            ("💰 Best Deals", "m_deals"),
            ("🏆 Top Sellers", "m_sellers"),
        ],
    ]

    all_cats = [
        (r["name"], f"cat:{r['id']}")
        for r in rows
    ]

    buttons.extend(
        [
            all_cats[i:i + 3]
            for i in range(0, len(all_cats), 3)
        ]
    )

    buttons.append(
        [("⬅️ Main Menu", "home")]
    )

    await q.message.edit_text(
        MARKET_TEXT,
        reply_markup=K(buttons),
    )

    await q.answer()


@dp.callback_query(F.data == "m_search")
async def m_search(q: CallbackQuery):
    await q.message.edit_text(
        "🔍 **Product Search**\n\n"
        "Send keyword or use filters:",
        reply_markup=K(
            [
                [("📊 Categories", "market"), ("⬅️ Back", "market")]
            ]
        ),
    )

    await q.answer()


@dp.callback_query(
    F.data.in_(
        [
            "m_trend",
            "m_top",
            "m_new",
            "m_deals",
            "m_sellers",
        ]
    )
)
async def m_filters(q: CallbackQuery):
    c = con()

    if q.data == "m_trend":
        ps = c.execute(
            """
            SELECT *
            FROM products
            WHERE status='approved'
            ORDER BY sold_count DESC
            LIMIT 10
            """
        ).fetchall()

        title = "🔥 Trending Products"

    elif q.data == "m_top":
        ps = c.execute(
            """
            SELECT *
            FROM products
            WHERE status='approved'
            ORDER BY rating DESC
            LIMIT 10
            """
        ).fetchall()

        title = "⭐ Top Rated Products"

    elif q.data == "m_new":
        ps = c.execute(
            """
            SELECT *
            FROM products
            WHERE status='approved'
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

        title = "🆕 Recently Listed Products"

    elif q.data == "m_deals":
        ps = c.execute(
            """
            SELECT *
            FROM products
            WHERE status='approved'
            ORDER BY CAST(price AS REAL) ASC
            LIMIT 10
            """
        ).fetchall()

        title = "💰 Best Deals"

    else:
        c.close()

        return await q.message.edit_text(
            "🏆 Top Sellers list is based on completed seller orders.",
            reply_markup=K(
                [[("⬅️ Back", "market")]]
            ),
        )

    c.close()

    b = [
        [
            (
                f"🛒 {p['name']} — "
                f"{p['price']} {CURRENCY}",
                f"prod:{p['id']}",
            )
        ]
        for p in ps
    ]

    b.append(
        [("⬅️ Back to Marketplace", "market")]
    )

    await q.message.edit_text(
        f"📂 **{title}**",
        reply_markup=K(b),
        parse_mode="Markdown",
    )

    await q.answer()


@dp.callback_query(F.data.startswith("cat:"))
async def cat(q: CallbackQuery):
    try:
        cid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await q.answer(
            "Invalid category.",
            show_alert=True,
        )

    c = con()

    subs = c.execute(
        """
        SELECT *
        FROM categories
        WHERE parent_id=?
        AND active=1
        """,
        (cid,),
    ).fetchall()

    ps = c.execute(
        """
        SELECT *
        FROM products
        WHERE category_id=?
        AND status='approved'
        ORDER BY id DESC
        LIMIT 20
        """,
        (cid,),
    ).fetchall()

    c.close()

    b = [
        [(s["name"], f"cat:{s['id']}")]
        for s in subs
    ]

    b += [
        [
            (
                f"🛒 {p['name']} — "
                f"{p['price']} {CURRENCY}",
                f"prod:{p['id']}",
            )
        ]
        for p in ps
    ]

    b.append(
        [("⬅️ Back", "market")]
    )

    await q.message.edit_text(
        "📂 Select subcategory or product:",
        reply_markup=K(
            b
            or [
                [("No products available", "noop")],
                [("⬅️ Back", "market")],
            ]
        ),
    )

    await q.answer()


@dp.callback_query(F.data.startswith("prod:"))
async def prod(q: CallbackQuery):
    try:
        pid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await q.answer(
            "Invalid product.",
            show_alert=True,
        )

    c = con()

    p = c.execute(
        "SELECT * FROM products WHERE id=?",
        (pid,),
    ).fetchone()

    seller = None

    if p:
        seller = c.execute(
            "SELECT * FROM users WHERE id=?",
            (p["seller_id"],),
        ).fetchone()

    c.close()

    if not p:
        return await q.answer(
            "Product unavailable",
            show_alert=True,
        )

    s_uname = (
        seller["username"]
        if seller and seller["username"]
        else ""
    )

    s_name = (
        f"@{s_uname}"
        if s_uname
        else f"User_{p['seller_id']}"
    )

    desc = (
        p["description"]
        if p["description"]
        else "No description"
    )

    seller_link = (
        f"https://t.me/{s_uname}"
        if s_uname
        else REQUIRED_CHANNEL_URL
    )

    text = (
        f"🤖 **{p['name']}**\n"
        f"💰 **Price:** {p['price']} {CURRENCY}\n"
        f"⭐ **Rating:** {p['rating']} / 5.0 "
        f"({p['reviews_count']} Reviews)\n"
        f"🛒 **Sold:** {p['sold_count']} Units\n"
        f"👤 **Seller:** [{s_name}]({seller_link})\n"
        f"📍 **Location:** Global\n"
        f"🟢 **Status:** Online\n"
        f"🛡️ **Escrow Protected:** 100% Safe\n\n"
        f"📝 **Description:**\n{desc}\n\n"
        f"📦 **Stock Available:** {p['stock']}"
    )

    markup = K(
        [
            [
                ("🛒 Buy Now", f"buy:{pid}"),
                ("⭐ Favorite", f"fav:{pid}"),
            ],
            [
                (
                    "👤 Seller Profile",
                    f"seller_prof:{p['seller_id']}",
                )
            ],
            [
                (
                    "⬅️ Back to Marketplace",
                    "market",
                )
            ],
        ]
    )

    await q.message.edit_text(
        text,
        reply_markup=markup,
        parse_mode="Markdown",
    )

    await q.answer()


@dp.callback_query(F.data.startswith("buy:"))
async def buy(q: CallbackQuery):
    try:
        pid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await q.answer(
            "Invalid product.",
            show_alert=True,
        )

    c = con()

    try:
        c.execute("BEGIN IMMEDIATE")

        p = c.execute(
            """
            SELECT *
            FROM products
            WHERE id=?
            AND status='approved'
            """,
            (pid,),
        ).fetchone()

        u = c.execute(
            "SELECT * FROM users WHERE id=?",
            (q.from_user.id,),
        ).fetchone()

        if not p:
            c.rollback()
            return await q.answer(
                "Product unavailable.",
                show_alert=True,
            )

        if not u:
            c.rollback()
            register(q.from_user)

            return await q.answer(
                "Please try again.",
                show_alert=True,
            )

        if p["stock"] < 1:
            c.rollback()
            return await q.answer(
                "Out of stock",
                show_alert=True,
            )

        price = dec(p["price"])

        if price <= 0:
            c.rollback()
            return await q.answer(
                "Invalid product price.",
                show_alert=True,
            )

        balance = dec(u["balance"])

        if balance < price:
            c.rollback()
            return await q.answer(
                "Insufficient balance! Please deposit.",
                show_alert=True,
            )

        new_balance = balance - price

        c.execute(
            """
            UPDATE users
            SET balance=?
            WHERE id=?
            """,
            (
                str(new_balance),
                u["id"],
            ),
        )

        cur = c.execute(
            """
            UPDATE products
            SET stock=stock-1,
                sold_count=sold_count+1
            WHERE id=?
            AND stock>0
            """,
            (pid,),
        )

        if cur.rowcount != 1:
            c.rollback()
            return await q.answer(
                "Product just went out of stock.",
                show_alert=True,
            )

        cur = c.execute(
            """
            INSERT INTO orders(
                buyer_id,
                product_id,
                seller_id,
                qty,
                amount,
                status,
                created_at
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                u["id"],
                pid,
                p["seller_id"],
                1,
                str(price),
                "escrow_pending",
                now(),
            ),
        )

        oid = cur.lastrowid

        c.execute(
            """
            INSERT INTO transactions(
                user_id,
                kind,
                amount,
                status,
                note,
                created_at
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                u["id"],
                "purchase",
                str(price),
                "completed",
                f"Order #{oid}",
                now(),
            ),
        )

        c.commit()

    except Exception:
        c.rollback()
        raise

    finally:
        c.close()

    await q.message.edit_text(
        f"✅ **Order Created & Protected by Escrow!**\n\n"
        f"📌 Order ID: #{oid}\n"
        f"🛍 Product: {p['name']}\n"
        f"💵 Amount: {price} {CURRENCY}\n"
        f"🛡️ Status: Escrow Holding Funds\n\n"
        f"Waiting for seller delivery...",
        reply_markup=K(
            [
                [
                    ("📦 My Orders", "orders"),
                    (
                        "✅ Confirm Delivery & Pay Seller",
                        f"confirm_order:{oid}",
                    ),
                ],
                [
                    ("🛍️ Marketplace", "market")
                ],
            ]
        ),
    )

    await q.answer()


@dp.callback_query(F.data.startswith("confirm_order:"))
async def confirm_order(q: CallbackQuery):
    try:
        oid = int(
            q.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        return await q.answer(
            "Invalid order.",
            show_alert=True,
        )

    c = con()

    try:
        c.execute("BEGIN IMMEDIATE")

        order = c.execute(
            """
            SELECT *
            FROM orders
            WHERE id=?
            AND buyer_id=?
            """,
            (
                oid,
                q.from_user.id,
            ),
        ).fetchone()

        if not order:
            c.rollback()
            return await q.answer(
                "Invalid order.",
                show_alert=True,
            )

        if order["status"] == "completed":
            c.rollback()
            return await q.answer(
                "Order already completed.",
                show_alert=True,
            )

        if order["status"] != "escrow_pending":
            c.rollback()
            return await q.answer(
                "This order cannot be completed.",
                show_alert=True,
            )

        amount = dec(order["amount"])
        seller_id = order["seller_id"]

        commission = (
            amount * Decimal("0.10")
        ).quantize(Decimal("0.01"))

        seller_payout = amount - commission

        c.execute(
            """
            UPDATE orders
            SET status='completed'
            WHERE id=?
            AND status='escrow_pending'
            """,
            (oid,),
        )

        c.execute(
            """
            UPDATE users
            SET balance = CAST(balance AS REAL) + ?
            WHERE id=?
            """,
            (
                str(seller_payout),
                seller_id,
            ),
        )

        c.commit()

    except Exception:
        c.rollback()
        raise

    finally:
        c.close()

    await q.message.edit_text(
        f"🎉 **Order Completed Successfully!**\n\n"
        f"Order #{oid} confirmed. Funds released to seller.\n"
        f"Please leave a review for this product!",
        reply_markup=K(
            [
                [
                    (
                        "⭐ Leave Review",
                        f"review:{order['product_id']}",
                    ),
                    (
                        "🛍️ Marketplace",
                        "market",
                    ),
                ]
            ]
        ),
    )

    await q.answer()


@dp.callback_query(F.data.startswith("review:"))
async def review_prompt(q: CallbackQuery):
    try:
        pid = int(
            q.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        return await q.answer(
            "Invalid product.",
            show_alert=True,
        )

    await q.message.edit_text(
        "⭐ Please send your review score and comment as:\n"
        "`/rate PRODUCT_ID 5 Great service!`",
        reply_markup=K(
            [[("⬅️ Marketplace", "market")]]
        ),
    )

    await q.answer()


@dp.message(Command("rate"))
async def rate_product(m: Message):
    parts = (m.text or "").split(maxsplit=2)

    if len(parts) < 3:
        return await m.answer(
            "Usage: /rate PRODUCT_ID 5 Review comment"
        )

    try:
        pid = int(parts[1])

        review_parts = parts[2].split(
            maxsplit=1
        )

        rating = int(review_parts[0])

        if rating < 1 or rating > 5:
            raise ValueError

        comment = (
            review_parts[1].strip()
            if len(review_parts) > 1
            else "Good"
        )

    except (ValueError, InvalidOperation):
        return await m.answer(
            "Invalid format. Rating must be between 1 and 5."
        )

    c = con()

    product = c.execute(
        """
        SELECT id
        FROM products
        WHERE id=?
        """,
        (pid,),
    ).fetchone()

    if not product:
        c.close()

        return await m.answer(
            "Product not found."
        )

    already = c.execute(
        """
        SELECT id
        FROM reviews
        WHERE product_id=?
        AND buyer_id=?
        """,
        (
            pid,
            m.from_user.id,
        ),
    ).fetchone()

    if already:
        c.close()

        return await m.answer(
            "You have already reviewed this product."
        )

    completed_order = c.execute(
        """
        SELECT id
        FROM orders
        WHERE product_id=?
        AND buyer_id=?
        AND status='completed'
        LIMIT 1
        """,
        (
            pid,
            m.from_user.id,
        ),
    ).fetchone()

    if not completed_order:
        c.close()

        return await m.answer(
            "❌ You can review only a product you purchased and completed."
        )

    c.execute(
        """
        INSERT INTO reviews(
            product_id,
            buyer_id,
            rating,
            comment,
            created_at
        )
        VALUES(?,?,?,?,?)
        """,
        (
            pid,
            m.from_user.id,
            rating,
            comment,
            now(),
        ),
    )

    avg = c.execute(
        """
        SELECT AVG(rating) AS avg,
               COUNT(*) AS cnt
        FROM reviews
        WHERE product_id=?
        """,
        (pid,),
    ).fetchone()

    c.execute(
        """
        UPDATE products
        SET rating=?,
            reviews_count=?
        WHERE id=?
        """,
        (
            round(avg["avg"], 1),
            avg["cnt"],
            pid,
        ),
    )

    c.commit()
    c.close()

    await m.answer(
        "✅ Thank you! Your review has been submitted successfully."
    )


@dp.callback_query(F.data == "orders")
async def orders(q: CallbackQuery):
    c = con()

    rs = c.execute(
        """
        SELECT
            o.id,
            o.amount,
            o.status,
            p.name
        FROM orders o
        JOIN products p
        ON p.id=o.product_id
        WHERE o.buyer_id=?
        ORDER BY o.id DESC
        LIMIT 20
        """,
        (q.from_user.id,),
    ).fetchall()

    c.close()

    text = (
        "📦 **My Orders**\n\n"
        +
        (
            "\n".join(
                f"#{r['id']} • {r['name']} • "
                f"{r['amount']} {CURRENCY} • "
                f"**{r['status']}**"
                for r in rs
            )
            if rs
            else "No orders yet."
        )
    )

    await q.message.edit_text(
        text,
        reply_markup=K(
            [
                [("🛍️ Marketplace", "market")],
                [("⬅️ Main Menu", "home")],
            ]
        ),
    )

    await q.answer()


@dp.callback_query(F.data == "wallet")
async def wallet(q: CallbackQuery):
    c = con()

    u = c.execute(
        "SELECT balance FROM users WHERE id=?",
        (q.from_user.id,),
    ).fetchone()

    c.close()

    if not u:
        register(q.from_user)

        balance = "0"
    else:
        balance = u["balance"]

    await q.message.edit_text(
        f"💰 **My Wallet**\n\n"
        f"Balance: {balance} {CURRENCY}\n\n"
        f"➕ Deposit: /deposit AMOUNT\n"
        f"💸 Withdraw: /withdraw AMOUNT DETAILS",
        reply_markup=K(
            [[("⬅️ Main Menu", "home")]]
        ),
    )

    await q.answer()


@dp.message(Command("deposit"))
async def deposit(m: Message):
    register(m.from_user)

    p = (m.text or "").split()

    if len(p) != 2:
        return await m.answer(
            "Usage: /deposit 25"
        )

    try:
        a = dec(p[1])

        if a <= 0:
            raise ValueError

    except (InvalidOperation, ValueError):
        return await m.answer(
            "Invalid amount"
        )

    c = con()

    min_deposit_row = c.execute(
        """
        SELECT value
        FROM settings
        WHERE key='min_deposit'
        """
    ).fetchone()

    min_deposit = (
        dec(min_deposit_row["value"])
        if min_deposit_row
        else Decimal("0")
    )

    if a < min_deposit:
        c.close()

        return await m.answer(
            f"Minimum deposit is {min_deposit} {CURRENCY}."
        )

    cur = c.execute(
        """
        INSERT INTO transactions(
            user_id,
            kind,
            amount,
            status,
            note,
            created_at
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            m.from_user.id,
            "deposit",
            str(a),
            "pending",
            "Manual deposit",
            now(),
        ),
    )

    tid = cur.lastrowid

    c.commit()
    c.close()

    await m.answer(
        f"⏳ Deposit request #{tid} submitted "
        f"for {a} {CURRENCY}."
    )

    if ADMIN_ID:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💰 Deposit #{tid}\n"
                f"User: {m.from_user.id}\n"
                f"Amount: {a}\n"
                f"/approve_deposit {tid}"
            ),
        )


@dp.message(Command("withdraw"))
async def withdraw(m: Message):
    register(m.from_user)

    p = (m.text or "").split(
        maxsplit=2
    )

    if len(p) < 3:
        return await m.answer(
            "Usage: /withdraw 25 DETAILS"
        )

    try:
        a = dec(p[1])

        if a <= 0:
            raise ValueError

    except (InvalidOperation, ValueError):
        return await m.answer(
            "Invalid amount"
        )

    c = con()

    min_withdraw_row = c.execute(
        """
        SELECT value
        FROM settings
        WHERE key='min_withdraw'
        """
    ).fetchone()

    min_withdraw = (
        dec(min_withdraw_row["value"])
        if min_withdraw_row
        else Decimal("0")
    )

    if a < min_withdraw:
        c.close()

        return await m.answer(
            f"Minimum withdrawal is "
            f"{min_withdraw} {CURRENCY}."
        )

    try:
        c.execute("BEGIN IMMEDIATE")

        u = c.execute(
            """
            SELECT balance
            FROM users
            WHERE id=?
            """,
            (m.from_user.id,),
        ).fetchone()

        if not u:
            c.rollback()
            c.close()

            return await m.answer(
                "User not registered."
            )

        balance = dec(u["balance"])

        if balance < a:
            c.rollback()
            c.close()

            return await m.answer(
                "Insufficient balance"
            )

        new_balance = balance - a

        c.execute(
            """
            UPDATE users
            SET balance=?
            WHERE id=?
            """,
            (
                str(new_balance),
                m.from_user.id,
            ),
        )

        cur = c.execute(
            """
            INSERT INTO transactions(
                user_id,
                kind,
                amount,
                status,
                note,
                created_at
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                m.from_user.id,
                "withdrawal",
                str(a),
                "pending",
                p[2],
                now(),
            ),
        )

        tid = cur.lastrowid

        c.commit()

    except Exception:
        c.rollback()
        raise

    finally:
        c.close()

    await m.answer(
        f"⏳ Withdrawal #{tid} submitted."
    )

    if ADMIN_ID:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💸 Withdrawal #{tid}\n"
                f"User: {m.from_user.id}\n"
                f"Amount: {a}\n"
                f"Details: {p[2]}"
            ),
        )


@dp.callback_query(F.data == "seller")
async def seller(q: CallbackQuery):
    c = con()

    u = c.execute(
        """
        SELECT seller_status
        FROM users
        WHERE id=?
        """,
        (q.from_user.id,),
    ).fetchone()

    c.close()

    if not u:
        register(q.from_user)
        seller_status = "none"
    else:
        seller_status = u["seller_status"]

    if seller_status == "approved":
        await q.message.edit_text(
            "🤝 **Seller Center**\n\n"
            "Add products using "
            "`/addproduct CATEGORY_ID PRICE STOCK NAME | DESCRIPTION`",
            reply_markup=K(
                [
                    [
                        ("📦 My Products", "seller_products"),
                        ("📊 Sales", "seller_sales"),
                    ],
                    [("⬅️ Main Menu", "home")],
                ]
            ),
        )

    else:
        await q.message.edit_text(
            "🤝 **Become A Seller**\n\n"
            "Apply with "
            "`/seller_apply Your experience & what you sell`",
            reply_markup=K(
                [[("⬅️ Main Menu", "home")]]
            ),
        )

    await q.answer()


@dp.message(Command("seller_apply"))
async def seller_apply(m: Message):
    register(m.from_user)

    d = (m.text or "").partition(" ")[2].strip()

    if not d:
        return await m.answer(
            "Usage: /seller_apply Experience & products"
        )

    c = con()

    existing = c.execute(
        """
        SELECT id
        FROM seller_applications
        WHERE user_id=?
        AND status='pending'
        """,
        (m.from_user.id,),
    ).fetchone()

    if existing:
        c.close()

        return await m.answer(
            "⏳ You already have a pending seller application."
        )

    c.execute(
        """
        INSERT INTO seller_applications(
            user_id,
            details,
            created_at
        )
        VALUES(?,?,?)
        """,
        (
            m.from_user.id,
            d,
            now(),
        ),
    )

    c.execute(
        """
        UPDATE users
        SET seller_status='pending'
        WHERE id=?
        """,
        (m.from_user.id,),
    )

    c.commit()
    c.close()

    await m.answer(
        "⏳ Seller application submitted for review."
    )

    if ADMIN_ID:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🤝 Seller application\n"
                f"User: {m.from_user.id}\n"
                f"{d}\n"
                f"/approve_seller {m.from_user.id}"
            ),
        )


@dp.message(Command("addproduct"))
async def addproduct(m: Message):
    register(m.from_user)

    c = con()

    u = c.execute(
        """
        SELECT seller_status
        FROM users
        WHERE id=?
        """,
        (m.from_user.id,),
    ).fetchone()

    if not u or u["seller_status"] != "approved":
        c.close()

        return await m.answer(
            "❌ You must be an approved seller."
        )

    parts = (
        m.text or ""
    ).partition(" ")[2].split(
        maxsplit=3
    )

    if len(parts) < 4:
        c.close()

        return await m.answer(
            "Usage: `/addproduct CAT_ID PRICE STOCK NAME | DESCRIPTION`",
            parse_mode="Markdown",
        )

    try:
        cat_id = int(parts[0])
        price = dec(parts[1])
        stock = int(parts[2])

        if price <= 0 or stock < 0:
            raise ValueError

        name_desc = parts[3].split(
            "|",
            1,
        )

        name = name_desc[0].strip()

        desc = (
            name_desc[1].strip()
            if len(name_desc) > 1
            else ""
        )

        if not name:
            raise ValueError

    except (ValueError, InvalidOperation):
        c.close()

        return await m.answer(
            "Invalid parameters format."
        )

    category = c.execute(
        """
        SELECT id
        FROM categories
        WHERE id=?
        AND active=1
        """,
        (cat_id,),
    ).fetchone()

    if not category:
        c.close()

        return await m.answer(
            "Invalid category ID."
        )

    c.execute(
        """
        INSERT INTO products(
            name,
            description,
            category_id,
            price,
            stock,
            seller_id,
            status,
            created_at
        )
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            name,
            desc,
            cat_id,
            str(price),
            stock,
            m.from_user.id,
            "approved",
            now(),
        ),
    )

    c.commit()
    c.close()

    await m.answer(
        "✅ Product listed successfully on marketplace!"
    )


@dp.callback_query(F.data == "referral")
async def referral(q: CallbackQuery):
    register(q.from_user)

    c = con()

    u = c.execute(
        """
        SELECT referral_earned
        FROM users
        WHERE id=?
        """,
        (q.from_user.id,),
    ).fetchone()

    n = c.execute(
        """
        SELECT COUNT(*) n
        FROM referrals
        WHERE referrer_id=?
        """,
        (q.from_user.id,),
    ).fetchone()["n"]

    c.close()

    if not u:
        earned = "0"
    else:
        earned = u["referral_earned"]

    me = await bot.get_me()

    link = (
        f"https://t.me/{me.username}"
        f"?start=ref_{q.from_user.id}"
    )

    await q.message.edit_text(
        f"🎁 **Referral Program**\n\n"
        f"👥 Referrals: {n}\n"
        f"💰 Earned: {earned} {CURRENCY}\n\n"
        f"🔗 `{link}`",
        reply_markup=K(
            [[("⬅️ Main Menu", "home")]]
        ),
        parse_mode="Markdown",
    )

    await q.answer()


@dp.callback_query(F.data == "support")
async def support(q: CallbackQuery):
    markup = K(
        [[("⬅️ Main Menu", "home")]]
    )

    text = (
        f"👨‍💻 **Admin Support**\n\n"
        f"Contact @{SUPPORT}"
        if SUPPORT
        else "Support not configured."
    )

    await q.message.edit_text(
        text,
        reply_markup=markup,
        parse_mode="Markdown",
    )

    await q.answer()


@dp.callback_query(F.data == "terms")
async def terms(q: CallbackQuery):
    await q.message.edit_text(
        "📜 **Terms And Rules**\n\n"
        "Only lawful and platform-compliant products/services are allowed. "
        "Escrow holds funds until delivery confirmation.",
        reply_markup=K(
            [[("⬅️ Main Menu", "home")]]
        ),
        parse_mode="Markdown",
    )

    await q.answer()


@dp.callback_query(F.data == "home")
async def home(q: CallbackQuery):
    await q.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu(),
    )

    await q.answer()


@dp.callback_query(F.data == "noop")
async def noop(q: CallbackQuery):
    await q.answer()


@dp.message(Command("approve_deposit"))
async def ad(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    p = (m.text or "").split()

    if len(p) != 2:
        return await m.answer(
            "Usage: /approve_deposit TRANSACTION_ID"
        )

    try:
        tid = int(p[1])
    except ValueError:
        return await m.answer(
            "Invalid transaction ID."
        )

    c = con()

    try:
        c.execute("BEGIN IMMEDIATE")

        tx = c.execute(
            """
            SELECT *
            FROM transactions
            WHERE id=?
            AND kind='deposit'
            AND status='pending'
            """,
            (tid,),
        ).fetchone()

        if not tx:
            c.rollback()
            return await m.answer(
                "Not found"
            )

        c.execute(
            """
            UPDATE users
            SET balance = CAST(balance AS REAL) + ?
            WHERE id=?
            """,
            (
                tx["amount"],
                tx["user_id"],
            ),
        )

        c.execute(
            """
            UPDATE transactions
            SET status='completed'
            WHERE id=?
            AND status='pending'
            """,
            (tx["id"],),
        )

        c.commit()

    except Exception:
        c.rollback()
        raise

    finally:
        c.close()

    await m.answer(
        "Deposit approved"
    )

    await bot.send_message(
        chat_id=tx["user_id"],
        text=(
            f"✅ Deposit approved: "
            f"{tx['amount']} {CURRENCY}"
        ),
    )


@dp.message(Command("approve_seller"))
async def aseller(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    p = (m.text or "").split()

    if len(p) != 2:
        return await m.answer(
            "Usage: /approve_seller USER_ID"
        )

    try:
        user_id = int(p[1])
    except ValueError:
        return await m.answer(
            "Invalid USER_ID."
        )

    c = con()

    user = c.execute(
        "SELECT id FROM users WHERE id=?",
        (user_id,),
    ).fetchone()

    if not user:
        c.close()

        return await m.answer(
            "User not found."
        )

    c.execute(
        """
        UPDATE users
        SET seller_status='approved'
        WHERE id=?
        """,
        (user_id,),
    )

    c.execute(
        """
        UPDATE seller_applications
        SET status='approved'
        WHERE user_id=?
        AND status='pending'
        """,
        (user_id,),
    )

    c.commit()
    c.close()

    await m.answer(
        "Seller approved"
    )

    await bot.send_message(
        chat_id=user_id,
        text=(
            "✅ Seller application approved! "
            "You can now add products."
        ),
    )


@dp.message(Command("reset_cats"))
async def reset_cats(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    c = con()

    c.execute(
        "DROP TABLE IF EXISTS categories"
    )

    c.commit()
    c.close()

    init()

    await m.answer(
        "✅ Categories reset! Now type /seed"
    )


@dp.message(Command("seed"))
async def seed(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    c = con()

    main_cats = [
        "Accounts",
        "Crypto",
        "Flash Crypto",
        "Fiat Exchange",
        "Gift Cards",
        "Payment Card",
        "Pay Gateway",
        "Sms OTP",
        "SmmServer",
        "Subscription",
        "Vpn/Proxy",
        "Virtual Sim",
        "Esim",
        "Kyc",
        "D-Marketing",
        "Software",
        "SSN Document",
        "Hacking",
        "Gaming",
        "Course",
        "Custom Support",
    ]

    for cat_name in main_cats:
        c.execute(
            """
            INSERT INTO categories(
                name,
                parent_id
            )
            SELECT ?, NULL
            WHERE NOT EXISTS(
                SELECT 1
                FROM categories
                WHERE name=?
                AND parent_id IS NULL
            )
            """,
            (
                cat_name,
                cat_name,
            ),
        )

    sub_pairs = [
        (
            "Accounts",
            [
                "Gmail Accounts",
                "Facebook Accounts",
                "Telegram Accounts",
            ],
        ),
        (
            "Gift Cards",
            [
                "Google Play",
                "Apple",
                "Amazon",
            ],
        ),
        (
            "Sms OTP",
            [
                "Telegram OTP",
                "WhatsApp OTP",
                "Gmail OTP",
            ],
        ),
    ]

    for parent, subs in sub_pairs:
        r = c.execute(
            """
            SELECT id
            FROM categories
            WHERE name=?
            AND parent_id IS NULL
            """,
            (parent,),
        ).fetchone()

        if r:
            for s in subs:
                c.execute(
                    """
                    INSERT INTO categories(
                        name,
                        parent_id
                    )
                    SELECT ?, ?
                    WHERE NOT EXISTS(
                        SELECT 1
                        FROM categories
                        WHERE name=?
                        AND parent_id=?
                    )
                    """,
                    (
                        s,
                        r["id"],
                        s,
                        r["id"],
                    ),
                )

    c.commit()
    c.close()

    await m.answer(
        "✅ Custom Categories & Subcategories "
        "created successfully!"
    )


async def main():
    init()

    print("Bot is starting...")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
