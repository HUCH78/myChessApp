from db import (
    assign_tpns,
    create_round,
    delete_round,
    get_round,
    get_settings,
    load_games,
    load_players,
    load_rounds,
    save_pairings,
    set_round_status,
    set_tournament_status,
)
from pairing import berger_rounds, swiss_pairings
from standings import compute_player_stats


def planned_rounds(settings=None, players=None) -> int:
    settings = settings or get_settings()
    players = players if players is not None else load_players()
    active = [p for p in players if p["active"]]
    if settings["tournament_type"] == "round_robin":
        n = len(active)
        if n < 2:
            return 0
        return n if n % 2 else n - 1
    return int(settings["rounds"])


def attach_scores(players, games=None):
    games = games if games is not None else load_games()
    stats = compute_player_stats(players, games)
    enriched = []
    for player in players:
        row = dict(player)
        row["score"] = stats[player["id"]]["score"]
        enriched.append(row)
    return enriched


def start_tournament() -> str:
    settings = get_settings()
    if settings["status"] != "setup":
        return "Das Turnier wurde bereits gestartet."
    players = [p for p in load_players() if p["active"]]
    if len(players) < 2:
        return "Mindestens zwei aktive Teilnehmer sind nötig."
    if settings["tournament_type"] == "swiss" and int(settings["rounds"]) < 1:
        return "Bitte die Anzahl der Runden festlegen."
    ordered = sorted(
        players,
        key=lambda p: (-int(p["dwz"] or 0), (p["nachname"] or "").lower(), (p["vorname"] or "").lower()),
    )
    assign_tpns([p["id"] for p in ordered])
    set_tournament_status("running", current_round=0, top_board_color="W")
    return ""


def start_round() -> str:
    settings = get_settings()
    if settings["status"] != "running":
        return "Bitte zuerst das Turnier starten."
    rounds = load_rounds()
    if rounds and rounds[-1]["status"] != "completed":
        return "Bitte die laufende Runde zuerst abschließen oder abbrechen."
    total = planned_rounds(settings)
    nxt = settings["current_round"] + 1
    if nxt > total:
        return "Alle Runden sind bereits gespielt."
    create_round(nxt)
    set_tournament_status("running", current_round=nxt)
    return ""


def generate_pairings() -> str:
    settings = get_settings()
    rnd = get_round(settings["current_round"])
    if not rnd:
        return "Bitte zuerst eine Runde starten."
    if rnd["status"] == "completed":
        return "Die Runde ist bereits abgeschlossen."
    existing = load_games(rnd["id"])
    if existing:
        return "Paarungen sind bereits ermittelt. Runde abbrechen, um neu zu losen."

    players = attach_scores(load_players())
    games = load_games()
    try:
        if settings["tournament_type"] == "round_robin":
            active_ids = [p["id"] for p in players if p["active"]]
            all_rounds = berger_rounds(active_ids)
            index = rnd["number"] - 1
            if index >= len(all_rounds):
                return "Keine weitere Rundensystem-Paarung."
            boards = []
            board_no = 1
            for white_id, black_id, is_bye in all_rounds[index]:
                boards.append((board_no, white_id, black_id, is_bye))
                board_no += 1
        else:
            boards = swiss_pairings(
                players,
                games,
                rnd["number"],
                planned_rounds(settings, players),
                settings["top_board_color"],
            )
    except ValueError as exc:
        return str(exc)

    save_pairings(rnd["id"], boards)
    set_round_status(rnd["id"], "playing")
    return ""


def close_round() -> str:
    settings = get_settings()
    rnd = get_round(settings["current_round"])
    if not rnd:
        return "Keine offene Runde."
    games = load_games(rnd["id"])
    if not games:
        return "Bitte zuerst die Paarungen ermitteln."
    if any(not g.get("result") for g in games):
        return "Bitte alle Ergebnisse eingeben."
    set_round_status(rnd["id"], "completed")
    if settings["current_round"] >= planned_rounds(settings):
        set_tournament_status("finished")
    return ""


def close_and_next() -> str:
    error = close_round()
    if error:
        return error
    if get_settings()["status"] == "finished":
        return ""
    error = start_round()
    if error:
        return error
    return generate_pairings()


def abort_round() -> str:
    settings = get_settings()
    rnd = get_round(settings["current_round"])
    if not rnd:
        return "Keine Runde zum Abbrechen."
    if rnd["status"] == "completed":
        return "Abgeschlossene Runden können nicht abgebrochen werden."
    number = rnd["number"]
    delete_round(rnd["id"])
    set_tournament_status("running", current_round=number - 1)
    return ""
