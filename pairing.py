"""Paarung nach FIDE C.04.1 Grundregeln und Dutch-ähnlichem Ablauf (C.04.3)."""


def played_set(games):
    pairs = set()
    for game in games:
        if game.get("is_bye"):
            continue
        white_id, black_id = game.get("white_id"), game.get("black_id")
        if white_id and black_id:
            pairs.add(frozenset((white_id, black_id)))
    return pairs


def color_history(player_id: int, games):
    colors = []
    for game in sorted(games, key=lambda g: g.get("round_number", 0)):
        if game.get("is_bye") or not game.get("result"):
            continue
        if game.get("white_id") == player_id and game.get("black_id"):
            colors.append("W")
        elif game.get("black_id") == player_id and game.get("white_id"):
            colors.append("B")
    return colors


def had_full_point_unplayed(player_id: int, games) -> bool:
    for game in games:
        if game.get("result") != "1-0":
            continue
        if game.get("is_bye") and game.get("white_id") == player_id:
            return True
    return False


def colour_preference(colors):
    played = [c for c in colors if c in ("W", "B")]
    if not played:
        return None, "none"
    white = played.count("W")
    black = played.count("B")
    diff = white - black
    last_two = played[-2:] if len(played) >= 2 else []
    if diff > 1 or last_two == ["W", "W"]:
        return "B", "absolute"
    if diff < -1 or last_two == ["B", "B"]:
        return "W", "absolute"
    if diff == 1:
        return "B", "strong"
    if diff == -1:
        return "W", "strong"
    return ("B" if played[-1] == "W" else "W"), "mild"


def colour_difference(colors):
    played = [c for c in colors if c in ("W", "B")]
    return played.count("W") - played.count("B")


def assign_colors(higher, lower, top_board_color: str):
    pref_h, strength_h = colour_preference(higher["colors"])
    pref_l, strength_l = colour_preference(lower["colors"])

    if pref_h and pref_l and pref_h != pref_l:
        white = higher if pref_h == "W" else lower
        black = lower if white is higher else higher
        return white, black

    if pref_h and not pref_l:
        return (higher, lower) if pref_h == "W" else (lower, higher)
    if pref_l and not pref_h:
        return (lower, higher) if pref_l == "W" else (higher, lower)

    rank = {"absolute": 3, "strong": 2, "mild": 1, "none": 0}
    if pref_h and pref_l and pref_h == pref_l:
        if rank[strength_h] > rank[strength_l]:
            return (higher, lower) if pref_h == "W" else (lower, higher)
        if rank[strength_l] > rank[strength_h]:
            return (lower, higher) if pref_l == "W" else (higher, lower)
        if higher["tpn"] < lower["tpn"]:
            return (higher, lower) if pref_h == "W" else (lower, higher)
        return (lower, higher) if pref_l == "W" else (higher, lower)

    if not higher["colors"] and not lower["colors"]:
        if higher["tpn"] % 2 == 1:
            return (higher, lower) if top_board_color == "W" else (lower, higher)
        return (lower, higher) if top_board_color == "W" else (higher, lower)

    return (higher, lower) if higher["tpn"] < lower["tpn"] else (lower, higher)


def _absolute_clash(a, b, last_round: bool, max_score: float) -> bool:
    if last_round and (a["score"] > max_score / 2 or b["score"] > max_score / 2):
        return False
    pref_a, strength_a = colour_preference(a["colors"])
    pref_b, strength_b = colour_preference(b["colors"])
    return strength_a == "absolute" and strength_b == "absolute" and pref_a == pref_b


def _can_meet(a, b, played, last_round: bool, max_score: float) -> bool:
    if frozenset((a["id"], b["id"])) in played:
        return False
    return not _absolute_clash(a, b, last_round, max_score)


def berger_rounds(player_ids):
    ids = list(player_ids)
    bye = None
    if len(ids) % 2 == 1:
        ids.append(bye)
    n = len(ids)
    rounds = []
    circle = ids[:]
    for round_index in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = circle[i], circle[n - 1 - i]
            if a is None or b is None:
                player = b if a is None else a
                pairs.append((player, None, True))
                continue
            if round_index % 2 == 0:
                white, black = a, b
            else:
                white, black = b, a
            if i == 0 and round_index % 2 == 1:
                white, black = a, b
            pairs.append((white, black, False))
        rounds.append(pairs)
        circle = [circle[0], circle[-1]] + circle[1:-1]
    return rounds


def swiss_pairings(players, games, round_number: int, total_rounds: int, top_board_color: str):
    eligible = [p for p in players if p["active"]]
    if len(eligible) < 2:
        raise ValueError("Mindestens zwei aktive Teilnehmer werden für die Paarung benötigt.")

    played = played_set(games)
    last_round = round_number >= total_rounds
    max_score = float(total_rounds)

    for player in eligible:
        player["tpn"] = player.get("tpn") or (10_000 + player["id"])
        player["colors"] = color_history(player["id"], games)
        player["had_pab"] = had_full_point_unplayed(player["id"], games)

    remaining = sorted(eligible, key=lambda p: (-p["score"], p["tpn"]))
    pairings = []

    if len(remaining) % 2 == 1:
        bye_candidates = sorted(
            remaining,
            key=lambda p: (p["had_pab"], p["score"], -p["tpn"]),
        )
        bye_player = None
        for candidate in bye_candidates:
            if candidate["had_pab"]:
                continue
            bye_player = candidate
            break
        if bye_player is None:
            raise ValueError("Kein gültiger Freilos-Empfänger (FIDE C.04.1 Art. 4).")
        remaining = [p for p in remaining if p["id"] != bye_player["id"]]
        pairings.append((bye_player, None))

    if round_number == 1:
        ordered = sorted(remaining, key=lambda p: p["tpn"])
        half = len(ordered) // 2
        found = list(zip(ordered[:half], ordered[half:]))
    else:

        def try_pair(pool):
            if not pool:
                return []
            head = pool[0]
            for opponent in pool[1:]:
                if not _can_meet(head, opponent, played, last_round, max_score):
                    continue
                rest = try_pair(
                    [p for p in pool if p["id"] not in (head["id"], opponent["id"])]
                )
                if rest is not None:
                    return [(head, opponent)] + rest
            return None

        found = try_pair(remaining)
        if found is None:
            raise ValueError("Keine gültige Paarung ohne Wiederholungspartie gefunden.")
    pairings.extend(found)

    boards = []
    board = 1
    for a, b in pairings:
        if b is None:
            boards.append((board, a["id"], None, True))
        else:
            higher, lower = (a, b) if a["tpn"] < b["tpn"] else (b, a)
            white, black = assign_colors(higher, lower, top_board_color)
            boards.append((board, white["id"], black["id"], False))
        board += 1
    return boards
