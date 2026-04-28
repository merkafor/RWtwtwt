import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

TOKEN = "8750219642:AAEMzKg4COy5pJ1USXL1ZrvVCYYQrFQ6WMw"
CHANNEL_ID = -1003763420629  # ID твоего канала

DB_NAME = "football.db"


# ---------------- БАЗА ДАННЫХ ----------------

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE,
        name TEXT NOT NULL,
        team_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league TEXT,
        team1_id INTEGER,
        team2_id INTEGER,
        message_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS match_players (
        match_id INTEGER,
        player_id INTEGER,
        confirmed INTEGER DEFAULT 0,
        PRIMARY KEY(match_id, player_id)
    )
    """)

    conn.commit()
    conn.close()


# ---------------- ДОБАВЛЕНИЕ ДАННЫХ ----------------

def add_team(name):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO teams(name) VALUES (?)", (name,))
    conn.commit()
    conn.close()

def add_player(tg_id, name, team_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO players(tg_id, name, team_id) VALUES (?, ?, ?)", (tg_id, name, team_id))
    conn.commit()
    conn.close()


# ---------------- ФОРМИРОВАНИЕ МАТЧА ----------------

def generate_match_text(match_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT league, team1_id, team2_id FROM matches WHERE id=?
    """, (match_id,))
    league, team1_id, team2_id = cur.fetchone()

    text = f"{league}\n\n"

    for team_id in [team1_id, team2_id]:
        cur.execute("SELECT name FROM teams WHERE id=?", (team_id,))
        team_name = cur.fetchone()[0]

        text += f"{team_name}:\n"

        cur.execute("""
            SELECT players.name, match_players.confirmed
            FROM match_players
            JOIN players ON players.id = match_players.player_id
            WHERE match_players.match_id=? AND players.team_id=?
        """, (match_id, team_id))

        for name, confirmed in cur.fetchall():
            status = "Отписались ✅" if confirmed else "Не отписались ❌"
            text += f"{name} — {status}\n"

        text += "\n"

    conn.close()
    return text


async def create_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    league = "Premier League"
    team1_id = 1
    team2_id = 2

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO matches(league, team1_id, team2_id)
        VALUES (?, ?, ?)
    """, (league, team1_id, team2_id))
    match_id = cur.lastrowid

    cur.execute("SELECT id FROM players WHERE team_id IN (?, ?)", (team1_id, team2_id))
    players = cur.fetchall()

    for player_id in players:
        cur.execute("INSERT INTO match_players(match_id, player_id) VALUES (?, ?)", (match_id, player_id[0]))

    conn.commit()

    text = generate_match_text(match_id)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Отписаться в боте", callback_data=f"confirm_{match_id}")]
    ])

    msg = await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=text,
        reply_markup=keyboard
    )

    cur.execute("UPDATE matches SET message_id=? WHERE id=?", (msg.message_id, match_id))
    conn.commit()
    conn.close()

    await update.message.reply_text("Матч опубликован!")


# ---------------- ПОДТВЕРЖДЕНИЕ ----------------

async def confirm_participation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tg_id = query.from_user.id
    match_id = int(query.data.split("_")[1])

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT id FROM players WHERE tg_id=?", (tg_id,))
    player = cur.fetchone()

    if not player:
        await query.answer("Вы не зарегистрированы!", show_alert=True)
        conn.close()
        return

    player_id = player[0]

    cur.execute("""
        UPDATE match_players
        SET confirmed=1
        WHERE match_id=? AND player_id=?
    """, (match_id, player_id))

    conn.commit()

    new_text = generate_match_text(match_id)

    cur.execute("SELECT message_id FROM matches WHERE id=?", (match_id,))
    message_id = cur.fetchone()[0]

    await context.bot.edit_message_text(
        chat_id=CHANNEL_ID,
        message_id=message_id,
        text=new_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Отписаться в боте", callback_data=f"confirm_{match_id}")]
        ])
    )

    conn.close()
    await query.answer("Вы успешно отписались!")


# ---------------- ЗАПУСК ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает!")


def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create_match", create_match))
    app.add_handler(CallbackQueryHandler(confirm_participation, pattern="^confirm_"))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
