from pairing import color_history


def points_from_result(player_id: int, game) -> float:
    result = game.get("result")
    if not result:
        return 0.0
    if game.get("is_bye") and game.get("white_id") == player_id:
        return 1.0 if result == "1-0" else 0.0
    if game.get("white_id") == player_id:
        if result == "1-0":
            return 1.0
        if result == "1/2-1/2":
            return 0.5
        return 0.0
    if game.get("black_id") == player_id:
        if result == "0-1":
            return 1.0
        if result == "1/2-1/2":
            return 0.5
        return 0.0
    return 0.0


def opponent_id(player_id: int, game):
    if game.get("is_bye"):
        return None
    if game.get("white_id") == player_id:
        return game.get("black_id")
    if game.get("black_id") == player_id:
        return game.get("white_id")
    return None


def compute_player_stats(players, games):
    stats = {}
    for player in players:
        pid = player["id"]
        pts = 0.0
        wins = 0
        played_points = 0.0
        opponents = []
        for game in games:
            if game.get("white_id") != pid and game.get("black_id") != pid:
                continue
            gained = points_from_result(pid, game)
            pts += gained
            if not game.get("is_bye"):
                played_points += gained
            if gained == 1.0 and not game.get("is_bye"):
                wins += 1
            opp = opponent_id(pid, game)
            if opp:
                opponents.append(opp)
        stats[pid] = {
            **player,
            "score": pts,
            "wins": wins,
            "played_points": played_points,
            "opponents": opponents,
            "colors": color_history(pid, games),
        }
    for pid, row in stats.items():
        row["buchholz"] = sum(stats[opp]["score"] for opp in row["opponents"] if opp in stats)
    return stats


def direct_encounter(stats, player_a: int, player_b: int, games) -> float:
    points = 0.0
    for game in games:
        if not game.get("result") or game.get("is_bye"):
            continue
        ids = {game.get("white_id"), game.get("black_id")}
        if ids != {player_a, player_b}:
            continue
        points += points_from_result(player_a, game)
    return points


def standing_key(stats, player_id: int, tiebreaks, games, group_ids):
    row = stats[player_id]
    key = [-row["score"]]
    for tb in tiebreaks:
        if not tb or tb == "none":
            continue
        if tb == "buchholz":
            key.append(-row["buchholz"])
        elif tb == "wins":
            key.append(-row["wins"])
        elif tb == "direct":
            direct = sum(
                direct_encounter(stats, player_id, other, games)
                for other in group_ids
                if other != player_id
            )
            key.append(-direct)
    key.append(row.get("tpn") or 9999)
    return tuple(key)


def ranked_standings(players, games, tiebreaks):
    stats = compute_player_stats(players, games)
    ids = [p["id"] for p in players]
    ordered = sorted(ids, key=lambda pid: standing_key(stats, pid, tiebreaks, games, ids))
    rows = []
    for rank, pid in enumerate(ordered, start=1):
        row = stats[pid]
        rows.append({**row, "rank": rank})
    return rows


def format_points(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(value).replace(".5", "½")


def progress_rows(players, games, tiebreaks):
    standings = ranked_standings(players, games, tiebreaks)
    round_numbers = sorted({g["round_number"] for g in games})
    tpn_by_id = {p["id"]: p.get("tpn") or "" for p in players}
    rows = []
    for row in standings:
        pid = row["id"]
        cells = {
            "rank": row["rank"],
            "name": f"{row['vorname']} {row['nachname']}".strip(),
            "score": row["score"],
            "rounds": {},
        }
        for number in round_numbers:
            game = next(
                (
                    g
                    for g in games
                    if g["round_number"] == number
                    and (g.get("white_id") == pid or g.get("black_id") == pid)
                ),
                None,
            )
            if game is None:
                cells["rounds"][number] = "–"
                continue
            if game.get("is_bye"):
                cells["rounds"][number] = "+"
                continue
            if game.get("white_id") == pid:
                color = "w"
                opp = game.get("black_id")
            else:
                color = "s"
                opp = game.get("white_id")
            pts = points_from_result(pid, game) if game.get("result") else None
            opp_tpn = tpn_by_id.get(opp, "?")
            pts_text = format_points(pts) if pts is not None else "?"
            cells["rounds"][number] = f"{opp_tpn}{color} {pts_text}"
        rows.append(cells)
    return rows, round_numbers
