import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "chess.db"

TIEBREAK_NONE = "none"

TIEBREAK_OPTIONS = {
    TIEBREAK_NONE: "Keine",
    "buchholz": "Buchholz",
    "direct": "Direkter Vergleich",
    "wins": "Anzahl Siege",
}

PLAYER_CSV_HEADERS = ["ID", "Vorname", "Nachname", "Verein", "DWZ", "Status"]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _columns(conn: sqlite3.Connection, table: str):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vorname TEXT NOT NULL,
                nachname TEXT NOT NULL,
                verein TEXT NOT NULL,
                dwz INTEGER NOT NULL
            )
            """
        )
        player_cols = _columns(conn, "players")
        if "active" not in player_cols:
            conn.execute("ALTER TABLE players ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        if "tpn" not in player_cols:
            conn.execute("ALTER TABLE players ADD COLUMN tpn INTEGER")
        if "dsb_id" not in player_cols:
            conn.execute("ALTER TABLE players ADD COLUMN dsb_id TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                tournament_type TEXT NOT NULL DEFAULT 'swiss',
                rounds INTEGER NOT NULL DEFAULT 5,
                tiebreak1 TEXT NOT NULL DEFAULT 'buchholz',
                tiebreak2 TEXT NOT NULL DEFAULT 'direct',
                tiebreak3 TEXT NOT NULL DEFAULT 'wins',
                status TEXT NOT NULL DEFAULT 'setup',
                current_round INTEGER NOT NULL DEFAULT 0,
                top_board_color TEXT NOT NULL DEFAULT 'W'
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (id) VALUES (1)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL,
                board INTEGER NOT NULL,
                white_id INTEGER,
                black_id INTEGER,
                result TEXT,
                is_bye INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE,
                FOREIGN KEY (white_id) REFERENCES players(id),
                FOREIGN KEY (black_id) REFERENCES players(id)
            )
            """
        )
        conn.commit()


def get_settings():
    with get_connection() as conn:
        return dict(conn.execute("SELECT * FROM settings WHERE id = 1").fetchone())


def save_settings(tournament_type: str, rounds: int, tiebreak1: str, tiebreak2: str, tiebreak3: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE settings
            SET tournament_type = ?, rounds = ?, tiebreak1 = ?, tiebreak2 = ?, tiebreak3 = ?
            WHERE id = 1
            """,
            (tournament_type, rounds, tiebreak1, tiebreak2, tiebreak3),
        )
        conn.commit()


def set_tournament_status(status: str, current_round: int = None, top_board_color: str = None) -> None:
    with get_connection() as conn:
        if current_round is not None:
            conn.execute("UPDATE settings SET current_round = ? WHERE id = 1", (current_round,))
        if top_board_color is not None:
            conn.execute("UPDATE settings SET top_board_color = ? WHERE id = 1", (top_board_color,))
        conn.execute("UPDATE settings SET status = ? WHERE id = 1", (status,))
        conn.commit()


def cascade_tiebreaks(tb1: str, tb2: str, tb3: str):
    if tb1 == TIEBREAK_NONE:
        return TIEBREAK_NONE, TIEBREAK_NONE, TIEBREAK_NONE
    if tb2 == TIEBREAK_NONE:
        return tb1, TIEBREAK_NONE, TIEBREAK_NONE
    return tb1, tb2, tb3


def active_tiebreaks(settings) -> list:
    values = []
    for key in (settings.get("tiebreak1"), settings.get("tiebreak2"), settings.get("tiebreak3")):
        if not key or key == TIEBREAK_NONE:
            break
        values.append(key)
    return values


def add_player(vorname: str, nachname: str, verein: str, dwz: int, dsb_id: str = None, active: bool = True) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO players (vorname, nachname, verein, dwz, dsb_id, active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (vorname, nachname, verein, dwz, dsb_id, 1 if active else 0),
        )
        conn.commit()


def load_players():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, vorname, nachname, verein, dwz, active, tpn, dsb_id
            FROM players
            ORDER BY COALESCE(tpn, 9999), id
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_player(player_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, vorname, nachname, verein, dwz, active, tpn, dsb_id
            FROM players WHERE id = ?
            """,
            (player_id,),
        ).fetchone()
        return dict(row) if row else None


def update_player(player_id: int, vorname: str, nachname: str, verein: str, dwz: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE players
            SET vorname = ?, nachname = ?, verein = ?, dwz = ?
            WHERE id = ?
            """,
            (vorname, nachname, verein, dwz, player_id),
        )
        conn.commit()


def delete_player(player_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
        conn.commit()


def player_has_games(player_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM games WHERE white_id = ? OR black_id = ? LIMIT 1",
            (player_id, player_id),
        ).fetchone()
        return row is not None


def set_player_active(player_id: int, active: bool) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE players SET active = ? WHERE id = ?", (1 if active else 0, player_id))
        conn.commit()


def assign_tpns(ordered_ids) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE players SET tpn = NULL")
        for index, player_id in enumerate(ordered_ids, start=1):
            conn.execute("UPDATE players SET tpn = ? WHERE id = ?", (index, player_id))
        conn.commit()


def load_rounds():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM rounds ORDER BY number").fetchall()]


def get_round(number: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM rounds WHERE number = ?", (number,)).fetchone()
        return dict(row) if row else None


def create_round(number: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO rounds (number, status) VALUES (?, 'pairing')",
            (number,),
        )
        conn.commit()
        return int(cur.lastrowid)


def set_round_status(round_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE rounds SET status = ? WHERE id = ?", (status, round_id))
        conn.commit()


def delete_round(round_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM games WHERE round_id = ?", (round_id,))
        conn.execute("DELETE FROM rounds WHERE id = ?", (round_id,))
        conn.commit()


def load_games(round_id: int = None):
    with get_connection() as conn:
        if round_id is None:
            rows = conn.execute(
                """
                SELECT g.*, r.number AS round_number
                FROM games g
                JOIN rounds r ON r.id = g.round_id
                ORDER BY r.number, g.board
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT g.*, r.number AS round_number
                FROM games g
                JOIN rounds r ON r.id = g.round_id
                WHERE g.round_id = ?
                ORDER BY g.board
                """,
                (round_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def save_pairings(round_id: int, boards) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM games WHERE round_id = ?", (round_id,))
        for board, white_id, black_id, is_bye in boards:
            conn.execute(
                """
                INSERT INTO games (round_id, board, white_id, black_id, result, is_bye)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (round_id, board, white_id, black_id, "1-0" if is_bye else None, 1 if is_bye else 0),
            )
        conn.commit()


def set_game_result(game_id: int, result: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE games SET result = ? WHERE id = ?", (result, game_id))
        conn.commit()


def delete_all_players() -> str:
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM games LIMIT 1").fetchone():
            return "Bitte zuerst das Turnier abschließen. Dann kann die Teilnehmerliste gelöscht werden."
        conn.execute("DELETE FROM players")
        conn.commit()
    return ""


def reset_tournament_keep_players() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM games")
        conn.execute("DELETE FROM rounds")
        conn.execute("UPDATE players SET tpn = NULL")
        conn.execute(
            """
            UPDATE settings
            SET status = 'setup', current_round = 0
            WHERE id = 1
            """
        )
        conn.commit()
