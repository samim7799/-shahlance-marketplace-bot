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

# ============================================================
# ACCOUNTS MARKETPLACE MODULE
# Safe authorized-account marketplace
# Does NOT store passwords, cookies, session tokens or phishing data
# ============================================================

ACCOUNT_CATEGORIES = [
    ("📧 Gmail Accounts", "Gmail"),
    ("📘 Facebook Accounts", "Facebook"),
    ("💬 Telegram Accounts", "Telegram"),
    ("🎮 Gaming Accounts", "Gaming"),
    ("💼 Business Accounts", "Business"),
    ("🛒 Marketplace Accounts", "Marketplace"),
    ("📱 Social Media Accounts", "Social"),
    ("☁️ Cloud Accounts", "Cloud"),
    ("🎬 Creator Accounts", "Creator"),
    ("🔐 Licensed Accounts", "Licensed"),
    ("💻 Software Accounts", "Software"),
    ("📦 Other Authorized Accounts", "Other"),
]


def account_db():
    db = con()

    db.executescript("""
    CREATE TABLE IF NOT EXISTS account_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS account_sellers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        seller_code TEXT UNIQUE NOT NULL,
        nickname TEXT NOT NULL,
        verified INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        total_sales INTEGER DEFAULT 0,
        active_listings INTEGER DEFAULT 0,
        rating REAL DEFAULT 0,
        reviews_count INTEGER DEFAULT 0,
        replacement_policy TEXT DEFAULT 'none',
        joined_at TEXT NOT NULL,
        response_rate REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS account_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        price TEXT NOT NULL,
        quantity INTEGER DEFAULT 1,
        quality TEXT DEFAULT 'Standard',
        age_type TEXT DEFAULT 'Fresh',
        registration_method TEXT DEFAULT 'Manual',
        replacement_period INTEGER DEFAULT 0,
        delivery_method TEXT DEFAULT 'Manual',
        metadata TEXT DEFAULT '',
        rules TEXT DEFAULT '',
        stock INTEGER DEFAULT 1,
        rating REAL DEFAULT 0,
        reviews_count INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS account_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        seller_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        amount TEXT NOT NULL,
        status TEXT DEFAULT 'escrow_pending',
        delivery TEXT DEFAULT '',
        buyer_confirmed INTEGER DEFAULT 0,
        seller_paid INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        confirmed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS account_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER UNIQUE NOT NULL,
        product_id INTEGER NOT NULL,
        seller_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        review TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS account_replacements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        seller_id INTEGER NOT NULL,
        reason TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        admin_note TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        resolved_at TEXT
    );

    CREATE TABLE IF NOT EXISTS account_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT NOT NULL,
        target_type TEXT DEFAULT '',
        target_id INTEGER,
        details TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """)

    for name, slug in ACCOUNT_CATEGORIES:
        db.execute(
            """
            INSERT OR IGNORE INTO account_categories(name, slug)
            VALUES (?, ?)
            """,
            (name, slug)
        )

    db.commit()
    db.close()


def account_keyboard(rows, back="market"):
    kb = []

    for i in range(0, len(rows), 3):
        line = []

        for item in rows[i:i + 3]:
            text, callback = item
            line.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=callback
                )
            )

        kb.append(line)

    if back:
        kb.append([
            InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=back
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def account_seller_get(user_id):
    db = con()
    row = db.execute(
        "SELECT * FROM account_sellers WHERE user_id=?",
        (user_id,)
    ).fetchone()
    db.close()
    return row


def account_seller_by_id(seller_id):
    db = con()
    row = db.execute(
        "SELECT * FROM account_sellers WHERE id=?",
        (seller_id,)
    ).fetchone()
    db.close()
    return row


def account_product(product_id):
    db = con()
    row = db.execute(
        """
        SELECT
            p.*,
            c.name AS category_name,
            s.nickname AS seller_nickname,
            s.seller_code,
            s.verified AS seller_verified,
            s.rating AS seller_rating,
            s.reviews_count AS seller_reviews
        FROM account_products p
        JOIN account_categories c ON c.id=p.category_id
        JOIN account_sellers s ON s.id=p.seller_id
        WHERE p.id=? AND p.active=1
        """,
        (product_id,)
    ).fetchone()
    db.close()
    return row


# ------------------------------------------------------------
# ACCOUNTS HOME
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_home")
async def accounts_home(call: CallbackQuery):

    text = (
        "🏪 <b>Accounts Marketplace</b>\n\n"
        "Choose a category or browse products.\n\n"
        "🔎 Search by product ID, seller ID or keyword.\n"
        "📦 Thousands of products supported.\n"
        "⭐ Seller ratings and reviews available.\n"
        "🛡 Buyer protection through escrow."
    )

    buttons = [
        [
            InlineKeyboardButton(
                text="🔎 Search",
                callback_data="acc_search"
            ),
            InlineKeyboardButton(
                text="🔥 Popular",
                callback_data="acc_popular"
            )
        ],
        [
            InlineKeyboardButton(
                text="🆕 New",
                callback_data="acc_new"
            ),
            InlineKeyboardButton(
                text="⭐ Top Sellers",
                callback_data="acc_top_sellers"
            )
        ]
    ]

    cats = [
        (
            name,
            f"acc_cat:{i + 1}"
        )
        for i, (name, slug) in enumerate(ACCOUNT_CATEGORIES)
    ]

    for i in range(0, len(cats), 3):
        buttons.append([
            InlineKeyboardButton(
                text=x[0],
                callback_data=x[1]
            )
            for x in cats[i:i + 3]
        ])

    buttons.append([
        InlineKeyboardButton(
            text="👤 Seller Center",
            callback_data="acc_seller"
        )
    ])

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )
    await call.answer()


# ------------------------------------------------------------
# CATEGORY
# ------------------------------------------------------------

@dp.callback_query(F.data.startswith("acc_cat:"))
async def account_category(call: CallbackQuery):

    cid = int(call.data.split(":")[1])

    db = con()

    cat = db.execute(
        "SELECT * FROM account_categories WHERE id=?",
        (cid,)
    ).fetchone()

    rows = db.execute(
        """
        SELECT p.id, p.title, p.price, p.stock,
               p.quality, s.nickname
        FROM account_products p
        JOIN account_sellers s ON s.id=p.seller_id
        WHERE p.category_id=?
          AND p.active=1
          AND p.stock>0
          AND s.status='approved'
        ORDER BY p.created_at DESC
        LIMIT 10
        """,
        (cid,)
    ).fetchall()

    db.close()

    if not cat:
        await call.answer("Category not found.", show_alert=True)
        return

    text = f"📂 <b>{cat['name']}</b>\n\n"

    if not rows:
        text += "No products available."

    buttons = []

    for r in rows:
        buttons.append([
            InlineKeyboardButton(
                text=f"#{r['id']} • {r['title'][:25]} • {r['price']} {CURRENCY}",
                callback_data=f"acc_product:{r['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Accounts",
            callback_data="acc_home"
        )
    ])

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


# ------------------------------------------------------------
# PAGINATION
# ------------------------------------------------------------

@dp.callback_query(F.data.startswith("acc_page:"))
async def account_page(call: CallbackQuery):

    _, cid, page = call.data.split(":")
    cid = int(cid)
    page = int(page)

    per_page = 10
    offset = page * per_page

    db = con()

    rows = db.execute(
        """
        SELECT p.id, p.title, p.price, p.stock
        FROM account_products p
        JOIN account_sellers s ON s.id=p.seller_id
        WHERE p.category_id=?
          AND p.active=1
          AND p.stock>0
          AND s.status='approved'
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (cid, per_page + 1, offset)
    ).fetchall()

    db.close()

    has_next = len(rows) > per_page
    rows = rows[:per_page]

    buttons = []

    for r in rows:
        buttons.append([
            InlineKeyboardButton(
                text=f"#{r['id']} • {r['title'][:28]} • {r['price']} {CURRENCY}",
                callback_data=f"acc_product:{r['id']}"
            )
        ])

    nav = []

    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"acc_page:{cid}:{page-1}"
            )
        )

    if has_next:
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"acc_page:{cid}:{page+1}"
            )
        )

    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Accounts",
            callback_data="acc_home"
        )
    ])

    await call.message.edit_text(
        f"📦 <b>Products</b>\nPage: {page + 1}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


# ------------------------------------------------------------
# PRODUCT DETAILS
# ------------------------------------------------------------

@dp.callback_query(F.data.startswith("acc_product:"))
async def account_product_details(call: CallbackQuery):

    pid = int(call.data.split(":")[1])
    p = account_product(pid)

    if not p:
        await call.answer(
            "Product unavailable.",
            show_alert=True
        )
        return

    verified = " ✅" if p["seller_verified"] else ""

    text = (
        f"📦 <b>{p['title']}</b>\n\n"
        f"🆔 Product ID: <code>{p['id']}</code>\n"
        f"📂 Category: {p['category_name']}\n"
        f"💰 Price: <b>{p['price']} {CURRENCY}</b>\n"
        f"📦 Stock: {p['stock']}\n"
        f"⭐ Quality: {p['quality']}\n"
        f"🕐 Type: {p['age_type']}\n"
        f"📝 Registration: {p['registration_method']}\n"
        f"🔄 Replacement: {p['replacement_period']} days\n"
        f"🚚 Delivery: {p['delivery_method']}\n\n"
        f"📄 <b>Description</b>\n"
        f"{p['description'] or 'No description'}\n\n"
        f"👤 Seller: <b>{p['seller_nickname']}</b>{verified}\n"
        f"🆔 Seller ID: <code>{p['seller_code']}</code>\n"
        f"⭐ Seller rating: {p['seller_rating']:.1f}/5\n"
        f"💬 Reviews: {p['seller_reviews']}"
    )

    if p["metadata"]:
        text += f"\n\nℹ️ <b>Metadata</b>\n{p['metadata']}"

    if p["rules"]:
        text += f"\n\n📜 <b>Rules</b>\n{p['rules']}"

    buttons = [
        [
            InlineKeyboardButton(
                text="👤 Seller Info",
                callback_data=f"acc_seller_profile:{p['seller_id']}"
            ),
            InlineKeyboardButton(
                text="⭐ Reviews",
                callback_data=f"acc_reviews:{p['seller_id']}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🛒 Buy",
                callback_data=f"acc_buy:{p['id']}"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Back",
                callback_data=f"acc_cat:{p['category_id']}"
            )
        ]
    ]

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


# ------------------------------------------------------------
# SELLER PROFILE
# ------------------------------------------------------------

@dp.callback_query(F.data.startswith("acc_seller_profile:"))
async def account_seller_profile(call: CallbackQuery):

    sid = int(call.data.split(":")[1])
    s = account_seller_by_id(sid)

    if not s:
        await call.answer(
            "Seller not found.",
            show_alert=True
        )
        return

    verified = "🟢 Verified" if s["verified"] else "⚪ Standard"

    text = (
        f"👤 <b>{s['nickname']}</b>\n\n"
        f"{verified}\n"
        f"🆔 Seller ID: <code>{s['seller_code']}</code>\n"
        f"📊 Total sales: {s['total_sales']}\n"
        f"📦 Active listings: {s['active_listings']}\n"
        f"⭐ Rating: {s['rating']:.1f}/5\n"
        f"💬 Reviews: {s['reviews_count']}\n"
        f"🔄 Replacement policy: {s['replacement_policy']}\n"
        f"📅 Joined: {s['joined_at'][:10]}\n"
        f"⚡ Response rate: {s['response_rate']:.0f}%\n\n"
        "🔒 Seller personal contact information is hidden."
    )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⭐ Reviews",
                        callback_data=f"acc_reviews:{sid}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Back",
                        callback_data="acc_home"
                    )
                ]
            ]
        )
    )

    await call.answer()


# ------------------------------------------------------------
# SELLER REVIEWS
# ------------------------------------------------------------

@dp.callback_query(F.data.startswith("acc_reviews:"))
async def account_reviews(call: CallbackQuery):

    sid = int(call.data.split(":")[1])

    db = con()

    rows = db.execute(
        """
        SELECT rating, review, created_at
        FROM account_reviews
        WHERE seller_id=?
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (sid,)
    ).fetchall()

    db.close()

    text = "⭐ <b>Seller Reviews</b>\n\n"

    if not rows:
        text += "No reviews yet."

    for r in rows:
        stars = "⭐" * int(r["rating"])
        text += (
            f"{stars}\n"
            f"{r['review'] or 'No written review'}\n"
            f"📅 {r['created_at'][:10]}\n\n"
        )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Back",
                        callback_data="acc_home"
                    )
                ]
            ]
        )
    )

    await call.answer()


# ------------------------------------------------------------
# BUY
# ------------------------------------------------------------

@dp.callback_query(F.data.startswith("acc_buy:"))
async def account_buy(call: CallbackQuery):

    pid = int(call.data.split(":")[1])
    p = account_product(pid)

    if not p:
        await call.answer(
            "Product unavailable.",
            show_alert=True
        )
        return

    if p["stock"] <= 0:
        await call.answer(
            "Out of stock.",
            show_alert=True
        )
        return

    if p["seller_id"] == call.from_user.id:
        await call.answer(
            "You cannot buy your own product.",
            show_alert=True
        )
        return

    text = (
        "🛒 <b>Confirm Purchase</b>\n\n"
        f"Product: {p['title']}\n"
        f"Product ID: {p['id']}\n"
        f"Price: <b>{p['price']} {CURRENCY}</b>\n"
        f"Stock: {p['stock']}\n\n"
        "Your balance will be charged and the order will enter escrow."
    )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Confirm Buy",
                        callback_data=f"acc_confirm:{pid}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Cancel",
                        callback_data=f"acc_product:{pid}"
                    )
                ]
            ]
        )
    )

    await call.answer()


# ------------------------------------------------------------
# CONFIRM PURCHASE
# ------------------------------------------------------------

@dp.callback_query(F.data.startswith("acc_confirm:"))
async def account_confirm(call: CallbackQuery):

    pid = int(call.data.split(":")[1])
    uid = call.from_user.id

    db = con()

    try:
        db.execute("BEGIN IMMEDIATE")

        p = db.execute(
            """
            SELECT p.*, s.status AS seller_status
            FROM account_products p
            JOIN account_sellers s ON s.id=p.seller_id
            WHERE p.id=? AND p.active=1
            """,
            (pid,)
        ).fetchone()

        if not p:
            db.rollback()
            await call.answer(
                "Product unavailable.",
                show_alert=True
            )
            return

        if p["stock"] <= 0:
            db.rollback()
            await call.answer(
                "Out of stock.",
                show_alert=True
            )
            return

        if p["seller_status"] != "approved":
            db.rollback()
            await call.answer(
                "Seller is not active.",
                show_alert=True
            )
            return

        price = dec(p["price"])

        user = db.execute(
            "SELECT balance FROM users WHERE user_id=?",
            (uid,)
        ).fetchone()

        if not user:
            db.rollback()
            await call.answer(
                "User account not found.",
                show_alert=True
            )
            return

        balance = dec(user["balance"])

        if balance < price:
            db.rollback()
            await call.answer(
                "Insufficient balance.",
                show_alert=True
            )
            return

        db.execute(
            """
            UPDATE users
            SET balance=?
            WHERE user_id=?
            """,
            (str(balance - price), uid)
        )

        new_stock = p["stock"] - 1

        db.execute(
            """
            UPDATE account_products
            SET stock=?, active=CASE WHEN ? <= 0 THEN 0 ELSE active END
            WHERE id=?
            """,
            (new_stock, new_stock, pid)
        )

        db.execute(
            """
            INSERT INTO account_orders
            (
                buyer_id,
                product_id,
                seller_id,
                quantity,
                amount,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'escrow_pending', ?)
            """,
            (
                uid,
                pid,
                p["seller_id"],
                1,
                str(price),
                now()
            )
        )

        order_id = db.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        try:
            db.execute(
                """
                INSERT INTO transactions
                (user_id, amount, kind, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    uid,
                    str(-price),
                    "account_purchase",
                    now()
                )
            )
        except Exception:
            pass

        db.commit()

    except Exception:
        db.rollback()
        await call.answer(
            "Purchase failed.",
            show_alert=True
        )
        db.close()
        return

    db.close()

    await call.message.edit_text(
        "✅ <b>Order Created</b>\n\n"
        f"🧾 Order ID: <code>{order_id}</code>\n"
        f"📦 Product ID: <code>{pid}</code>\n\n"
        "💰 Payment is held in escrow.\n"
        "📨 Seller must provide the delivery.\n"
        "✅ After receiving the product, confirm the order."
    )

    await call.answer("Order created.")


# ------------------------------------------------------------
# MY ORDERS
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_orders")
async def account_orders(call: CallbackQuery):

    db = con()

    rows = db.execute(
        """
        SELECT
            o.id,
            o.amount,
            o.status,
            o.created_at,
            p.title
        FROM account_orders o
        JOIN account_products p ON p.id=o.product_id
        WHERE o.buyer_id=?
        ORDER BY o.id DESC
        LIMIT 20
        """,
        (call.from_user.id,)
    ).fetchall()

    db.close()

    text = "🧾 <b>My Account Orders</b>\n\n"

    if not rows:
        text += "No orders."

    buttons = []

    for r in rows:
        text += (
            f"#{r['id']} • {r['title'][:25]}\n"
            f"💰 {r['amount']} {CURRENCY} • {r['status']}\n\n"
        )

        if r["status"] == "delivered":
            buttons.append([
                InlineKeyboardButton(
                    text=f"✅ Confirm #{r['id']}",
                    callback_data=f"acc_order_confirm:{r['id']}"
                )
            ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Accounts",
            callback_data="acc_home"
        )
    ])

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


# ------------------------------------------------------------
# CONFIRM ORDER
# ------------------------------------------------------------

@dp.callback_query(F.data.startswith("acc_order_confirm:"))
async def account_order_confirm(call: CallbackQuery):

    oid = int(call.data.split(":")[1])
    uid = call.from_user.id

    db = con()

    order = db.execute(
        """
        SELECT *
        FROM account_orders
        WHERE id=? AND buyer_id=?
        """,
        (oid, uid)
    ).fetchone()

    if not order:
        db.close()
        await call.answer(
            "Order not found.",
            show_alert=True
        )
        return

    if order["status"] != "delivered":
        db.close()
        await call.answer(
            "Order is not ready for confirmation.",
            show_alert=True
        )
        return

    # Marketplace commission
    amount = dec(order["amount"])
    commission = amount * Decimal("0.10")
    seller_amount = amount - commission

    seller = db.execute(
        """
        SELECT user_id
        FROM account_sellers
        WHERE id=?
        """,
        (order["seller_id"],)
    ).fetchone()

    if not seller:
        db.close()
        await call.answer(
            "Seller unavailable.",
            show_alert=True
        )
        return

    seller_user = db.execute(
        """
        SELECT balance
        FROM users
        WHERE user_id=?
        """,
        (seller["user_id"],)
    ).fetchone()

    if not seller_user:
        db.close()
        await call.answer(
            "Seller wallet unavailable.",
            show_alert=True
        )
        return

    new_balance = dec(seller_user["balance"]) + seller_amount

    db.execute(
        """
        UPDATE users
        SET balance=?
        WHERE user_id=?
        """,
        (str(new_balance), seller["user_id"])
    )

    db.execute(
        """
        UPDATE account_orders
        SET
            status='completed',
            buyer_confirmed=1,
            seller_paid=1,
            confirmed_at=?
        WHERE id=?
        """,
        (now(), oid)
    )

    db.execute(
        """
        UPDATE account_sellers
        SET total_sales=total_sales+1
        WHERE id=?
        """,
        (order["seller_id"],)
    )

    db.commit()
    db.close()

    await call.message.edit_text(
        "✅ <b>Order Completed</b>\n\n"
        f"Order ID: <code>{oid}</code>\n"
        "💰 Seller payment released.\n"
        "⭐ You can now leave a review using /rate."
    )

    await call.answer("Order confirmed.")


# ------------------------------------------------------------
# POPULAR
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_popular")
async def account_popular(call: CallbackQuery):

    db = con()

    rows = db.execute(
        """
        SELECT
            p.id,
            p.title,
            p.price,
            p.stock
        FROM account_products p
        JOIN account_sellers s ON s.id=p.seller_id
        WHERE p.active=1
          AND p.stock>0
          AND s.status='approved'
        ORDER BY p.reviews_count DESC,
                 p.rating DESC
        LIMIT 15
        """
    ).fetchall()

    db.close()

    buttons = [
        [
            InlineKeyboardButton(
                text=f"🔥 #{r['id']} • {r['title'][:25]} • {r['price']} {CURRENCY}",
                callback_data=f"acc_product:{r['id']}"
            )
        ]
        for r in rows
    ]

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Accounts",
            callback_data="acc_home"
        )
    ])

    await call.message.edit_text(
        "🔥 <b>Popular Accounts Products</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


# ------------------------------------------------------------
# NEW PRODUCTS
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_new")
async def account_new(call: CallbackQuery):

    db = con()

    rows = db.execute(
        """
        SELECT p.id, p.title, p.price
        FROM account_products p
        JOIN account_sellers s ON s.id=p.seller_id
        WHERE p.active=1
          AND p.stock>0
          AND s.status='approved'
        ORDER BY p.id DESC
        LIMIT 15
        """
    ).fetchall()

    db.close()

    buttons = [
        [
            InlineKeyboardButton(
                text=f"🆕 #{r['id']} • {r['title'][:25]} • {r['price']} {CURRENCY}",
                callback_data=f"acc_product:{r['id']}"
            )
        ]
        for r in rows
    ]

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Accounts",
            callback_data="acc_home"
        )
    ])

    await call.message.edit_text(
        "🆕 <b>New Products</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


# ------------------------------------------------------------
# TOP SELLERS
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_top_sellers")
async def account_top_sellers(call: CallbackQuery):

    db = con()

    rows = db.execute(
        """
        SELECT *
        FROM account_sellers
        WHERE status='approved'
        ORDER BY rating DESC,
                 total_sales DESC
        LIMIT 15
        """
    ).fetchall()

    db.close()

    buttons = []

    for r in rows:
        badge = "✅" if r["verified"] else "⭐"

        buttons.append([
            InlineKeyboardButton(
                text=f"{badge} {r['nickname']} • {r['rating']:.1f}",
                callback_data=f"acc_seller_profile:{r['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Accounts",
            callback_data="acc_home"
        )
    ])

    await call.message.edit_text(
        "⭐ <b>Top Sellers</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


# ------------------------------------------------------------
# SEARCH
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_search")
async def account_search_start(call: CallbackQuery):

    await call.message.answer(
        "🔎 <b>Accounts Search</b>\n\n"
        "Send one of these:\n"
        "• Product ID\n"
        "• Seller ID\n"
        "• Seller nickname\n"
        "• Category\n"
        "• Keyword\n\n"
        "Example: <code>gmail</code>"
    )

    await call.answer()


@dp.message()
async def account_search_message(message: Message):

    query = message.text.strip() if message.text else ""

    if not query:
        return

    # Ignore commands
    if query.startswith("/"):
        return

    db = con()

    rows = db.execute(
        """
        SELECT
            p.id,
            p.title,
            p.price,
            p.stock,
            c.name AS category_name,
            s.nickname,
            s.seller_code
        FROM account_products p
        JOIN account_categories c
            ON c.id=p.category_id
        JOIN account_sellers s
            ON s.id=p.seller_id
        WHERE p.active=1
          AND p.stock>0
          AND s.status='approved'
          AND (
              CAST(p.id AS TEXT)=?
              OR LOWER(p.title) LIKE ?
              OR LOWER(p.description) LIKE ?
              OR LOWER(c.name) LIKE ?
              OR LOWER(s.nickname) LIKE ?
              OR LOWER(s.seller_code) LIKE ?
          )
        ORDER BY p.id DESC
        LIMIT 20
        """,
        (
            query,
            f"%{query.lower()}%",
            f"%{query.lower()}%",
            f"%{query.lower()}%",
            f"%{query.lower()}%",
            f"%{query.lower()}%"
        )
    ).fetchall()

    db.close()

    # Don't hijack ordinary bot messages
    if not rows:
        return

    buttons = []

    for r in rows:
        buttons.append([
            InlineKeyboardButton(
                text=f"#{r['id']} • {r['title'][:25]} • {r['price']} {CURRENCY}",
                callback_data=f"acc_product:{r['id']}"
            )
        ])

    await message.answer(
        f"🔎 <b>Search Results</b>\n"
        f"Query: <code>{query}</code>\n\n"
        f"Found: {len(rows)}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# ============================================================
# SELLER CENTER
# ============================================================

@dp.callback_query(F.data == "acc_seller")
async def account_seller_center(call: CallbackQuery):

    seller = account_seller_get(call.from_user.id)

    if not seller:

        await call.message.edit_text(
            "👤 <b>Accounts Seller Center</b>\n\n"
            "You are not an Accounts seller yet.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📝 Apply as Seller",
                            callback_data="acc_seller_apply"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="⬅️ Accounts",
                            callback_data="acc_home"
                        )
                    ]
                ]
            )
        )

        await call.answer()
        return

    text = (
        "👤 <b>Seller Center</b>\n\n"
        f"Nickname: {seller['nickname']}\n"
        f"Seller ID: <code>{seller['seller_code']}</code>\n"
        f"Status: {seller['status']}\n"
        f"Verified: {'Yes' if seller['verified'] else 'No'}\n"
        f"⭐ Rating: {seller['rating']:.1f}\n"
        f"💰 Sales: {seller['total_sales']}\n"
        f"📦 Active listings: {seller['active_listings']}"
    )

    buttons = [
        [
            InlineKeyboardButton(
                text="➕ Add Product",
                callback_data="acc_add_product"
            ),
            InlineKeyboardButton(
                text="📦 My Products",
                callback_data="acc_my_products"
            )
        ],
        [
            InlineKeyboardButton(
                text="⭐ My Reviews",
                callback_data="acc_my_reviews"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Accounts",
                callback_data="acc_home"
            )
        ]
    ]

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


# ------------------------------------------------------------
# SELLER APPLY
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_seller_apply")
async def account_seller_apply(call: CallbackQuery):

    existing = account_seller_get(call.from_user.id)

    if existing:
        await call.answer(
            "Application already exists.",
            show_alert=True
        )
        return

    nickname = f"Seller{call.from_user.id % 100000:05d}"
    seller_code = f"ACC-{call.from_user.id % 1000000:06d}"

    db = con()

    db.execute(
        """
        INSERT INTO account_sellers
        (
            user_id,
            seller_code,
            nickname,
            status,
            joined_at
        )
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (
            call.from_user.id,
            seller_code,
            nickname,
            now()
        )
    )

    db.commit()
    db.close()

    await call.message.edit_text(
        "✅ <b>Seller Application Submitted</b>\n\n"
        f"Nickname: <b>{nickname}</b>\n"
        f"Seller ID: <code>{seller_code}</code>\n\n"
        "⏳ Admin approval is required."
    )

    await call.answer()


# ------------------------------------------------------------
# MY PRODUCTS
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_my_products")
async def account_my_products(call: CallbackQuery):

    seller = account_seller_get(call.from_user.id)

    if not seller:
        await call.answer(
            "Seller account not found.",
            show_alert=True
        )
        return

    db = con()

    rows = db.execute(
        """
        SELECT id, title, price, stock, active
        FROM account_products
        WHERE seller_id=?
        ORDER BY id DESC
        LIMIT 30
        """,
        (seller["id"],)
    ).fetchall()

    db.close()

    text = "📦 <b>My Products</b>\n\n"

    if not rows:
        text += "No products yet."

    for r in rows:
        status = "🟢" if r["active"] else "🔴"

        text += (
            f"{status} #{r['id']} {r['title'][:30]}\n"
            f"💰 {r['price']} {CURRENCY} | Stock: {r['stock']}\n\n"
        )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Add Product",
                        callback_data="acc_add_product"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Seller Center",
                        callback_data="acc_seller"
                    )
                ]
            ]
        )
    )

    await call.answer()


# ------------------------------------------------------------
# ADD PRODUCT
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_add_product")
async def account_add_product(call: CallbackQuery):

    seller = account_seller_get(call.from_user.id)

    if not seller or seller["status"] != "approved":
        await call.answer(
            "Your seller account must be approved first.",
            show_alert=True
        )
        return

    await call.message.answer(
        "➕ <b>Add Account Product</b>\n\n"
        "Use the following format:\n\n"
        "<code>\n"
        "category | title | description | price | quantity | quality | fresh/aged | registration | replacement_days | delivery | metadata | rules\n"
        "</code>\n\n"
        "Example:\n"
        "<code>\n"
        "Gmail | Gmail Premium | Authorized account | 10 | 1 | Premium | Fresh | Manual | 7 | Manual | Region: US | No abuse\n"
        "</code>\n\n"
        "⚠️ Do not include passwords, cookies, session tokens or other authentication secrets."
    )

    await call.answer()


# ------------------------------------------------------------
# MY REVIEWS
# ------------------------------------------------------------

@dp.callback_query(F.data == "acc_my_reviews")
async def account_my_reviews(call: CallbackQuery):

    seller = account_seller_get(call.from_user.id)

    if not seller:
        await call.answer(
            "Seller not found.",
            show_alert=True
        )
        return

    db = con()

    rows = db.execute(
        """
        SELECT rating, review, created_at
        FROM account_reviews
        WHERE seller_id=?
        ORDER BY id DESC
        LIMIT 20
        """,
        (seller["id"],)
    ).fetchall()

    db.close()

    text = "⭐ <b>My Reviews</b>\n\n"

    if not rows:
        text += "No reviews yet."

    for r in rows:
        text += (
            f"{'⭐' * r['rating']}\n"
            f"{r['review'] or 'No written review'}\n"
            f"{r['created_at'][:10]}\n\n"
        )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Seller Center",
                        callback_data="acc_seller"
                    )
                ]
            ]
        )
    )

    await call.answer()


# ============================================================
# ADMIN ACCOUNTS PANEL
# ============================================================

@dp.message(Command("accounts_admin"))
async def accounts_admin(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    db = con()

    sellers = db.execute(
        "SELECT COUNT(*) AS c FROM account_sellers"
    ).fetchone()["c"]

    pending = db.execute(
        """
        SELECT COUNT(*) AS c
        FROM account_sellers
        WHERE status='pending'
        """
    ).fetchone()["c"]

    products = db.execute(
        "SELECT COUNT(*) AS c FROM account_products"
    ).fetchone()["c"]

    orders = db.execute(
        "SELECT COUNT(*) AS c FROM account_orders"
    ).fetchone()["c"]

    replacements = db.execute(
        """
        SELECT COUNT(*) AS c
        FROM account_replacements
        WHERE status='pending'
        """
    ).fetchone()["c"]

    db.close()

    await message.answer(
        "🛠 <b>Accounts Admin Panel</b>\n\n"
        f"👤 Sellers: {sellers}\n"
        f"⏳ Pending sellers: {pending}\n"
        f"📦 Products: {products}\n"
        f"🧾 Orders: {orders}\n"
        f"🔄 Pending replacements: {replacements}\n\n"
        "Use:\n"
        "<code>/accounts_approve_seller SELLER_ID</code>"
    )


@dp.message(Command("accounts_approve_seller"))
async def accounts_approve_seller(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "Usage:\n"
            "<code>/accounts_approve_seller SELLER_ID</code>"
        )
        return

    try:
        seller_id = int(parts[1])
    except ValueError:
        await message.answer("Invalid Seller ID.")
        return

    db = con()

    seller = db.execute(
        """
        SELECT *
        FROM account_sellers
        WHERE id=?
        """,
        (seller_id,)
    ).fetchone()

    if not seller:
        db.close()
        await message.answer("Seller not found.")
        return

    db.execute(
        """
        UPDATE account_sellers
        SET status='approved',
            verified=1
        WHERE id=?
        """,
        (seller_id,)
    )

    db.execute(
        """
        INSERT INTO account_audit_logs
        (
            admin_id,
            action,
            target_type,
            target_id,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ADMIN_ID,
            "approve_seller",
            "seller",
            seller_id,
            "Accounts seller approved",
            now()
        )
    )

    db.commit()
    db.close()

    await message.answer(
        f"✅ Seller <code>{seller_id}</code> approved."
    )


# ============================================================
# ACCOUNT DB INITIALIZATION
# ============================================================

# IMPORTANT:
# In async def main(), immediately after:
#
#     init()
#
# add:
#
#     account_db()
#
# ============================================================
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
