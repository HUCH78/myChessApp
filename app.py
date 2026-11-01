import csv
import io

import pandas as pd
import streamlit as st

from db import (
    PLAYER_CSV_HEADERS,
    TIEBREAK_NONE,
    TIEBREAK_OPTIONS,
    active_tiebreaks,
    add_player,
    cascade_tiebreaks,
    delete_all_players,
    delete_player,
    get_player,
    get_settings,
    init_db,
    load_games,
    load_players,
    load_rounds,
    player_has_games,
    save_settings,
    set_game_result,
    set_player_active,
    update_player,
)
from dsb import search_players
from export_views import to_csv, to_html, to_pdf
from standings import format_points, progress_rows, ranked_standings
from tournament import (
    abort_round,
    attach_scores,
    close_and_next,
    finish_tournament,
    generate_pairings,
    planned_rounds,
    start_round,
    start_tournament,
)


def parse_dwz(raw: str):
    text = (raw or "").strip()
    if not text:
        return 0, None
    if not text.isdigit():
        return None, "Die DWZ muss eine ganze Zahl zwischen 0 und 3000 sein."
    value = int(text)
    if value > 3000:
        return None, "Die DWZ muss eine ganze Zahl zwischen 0 und 3000 sein."
    return value, None


def player_display_name(vorname: str, nachname: str) -> str:
    return f"{vorname} {nachname}".strip()


def name_by_id(players, player_id):
    if not player_id:
        return "Freilos"
    for player in players:
        if player["id"] == player_id:
            return player_display_name(player["vorname"], player["nachname"])
    return f"#{player_id}"


def score_map_before(players, games, round_number: int):
    prior = [g for g in games if g.get("round_number", 0) < round_number]
    return {row["id"]: row["score"] for row in attach_scores(players, prior)}


def name_with_score(players, player_id, scores):
    name = name_by_id(players, player_id)
    if not player_id:
        return name
    points = scores.get(player_id, 0)
    return f"{name} ({format_points(points)})"


FORM_KEYS = ("player_vorname", "player_nachname", "player_verein", "player_dwz")
DSB_KEYS = ("dsb_vn", "dsb_nn", "dsb_vkz")


def reset_player_form_state() -> None:
    for key in FORM_KEYS:
        st.session_state.pop(key, None)


def reset_dsb_form_state() -> None:
    for key in DSB_KEYS:
        st.session_state.pop(key, None)
    st.session_state.dsb_results = []
    st.session_state.dsb_error = None


st.set_page_config(page_title="Schachturnier", page_icon="♟️", layout="wide")
init_db()

if st.session_state.pop("clear_player_form", False):
    reset_player_form_state()
if st.session_state.pop("clear_dsb_form", False):
    reset_dsb_form_state()

settings = get_settings()
players = load_players()
games = load_games()
tiebreaks = active_tiebreaks(settings)


@st.dialog("Löschen bestätigen")
def confirm_delete_dialog(player_id: int, name: str) -> None:
    st.write(
        f"Möchten Sie **{name}** wirklich löschen? "
        "Dieser Schritt kann nicht rückgängig gemacht werden."
    )
    abbrechen, loeschen = st.columns(2)
    with abbrechen:
        if st.button("Abbrechen", width="stretch"):
            st.rerun()
    with loeschen:
        if st.button("Endgültig löschen", type="primary", width="stretch"):
            delete_player(player_id)
            st.session_state.flash_success = f"{name} wurde gelöscht."
            st.rerun()


@st.dialog("Teilnehmer bearbeiten")
def edit_player_dialog(player_id: int) -> None:
    player = get_player(player_id)
    if player is None:
        st.error("Teilnehmer wurde nicht gefunden.")
        if st.button("Schließen"):
            st.rerun()
        return

    vorname = st.text_input("Vorname *", value=player["vorname"])
    nachname = st.text_input("Nachname", value=player["nachname"])
    verein = st.text_input("Verein", value=player["verein"])
    dwz_raw = st.text_input("DWZ", value=str(player["dwz"]))

    abbrechen, speichern = st.columns(2)
    with abbrechen:
        if st.button("Abbrechen", width="stretch"):
            st.rerun()
    with speichern:
        if st.button("Speichern", type="primary", width="stretch"):
            vorname = vorname.strip()
            nachname = nachname.strip()
            verein = verein.strip()
            dwz_value, dwz_error = parse_dwz(dwz_raw)
            if not vorname:
                st.error("Bitte den Vornamen ausfüllen. Die übrigen Eingaben bleiben erhalten.")
            if dwz_error:
                st.error(dwz_error)
            if vorname and dwz_error is None:
                update_player(player_id, vorname, nachname, verein, dwz_value)
                st.session_state.flash_success = (
                    f"{player_display_name(vorname, nachname)} wurde gespeichert."
                )
                st.rerun()


@st.dialog("Ergebnis ändern")
def confirm_result_change_dialog(game_id: int, old_result: str, new_result: str, label: str) -> None:
    st.write(f"**{label}**")
    st.write(f"Ergebnis von **{old_result or 'offen'}** auf **{new_result}** ändern?")
    abbrechen, speichern = st.columns(2)
    with abbrechen:
        if st.button("Abbrechen", width="stretch"):
            st.session_state[f"res_{game_id}"] = old_result
            st.rerun()
    with speichern:
        if st.button("Änderung übernehmen", type="primary", width="stretch"):
            set_game_result(game_id, new_result)
            st.session_state.flash_success = "Ergebnis wurde geändert."
            st.rerun()


@st.dialog("Turnier abschließen")
def finish_tournament_dialog() -> None:
    st.write(
        "Beim Abschließen werden **alle Rundenergebnisse und Paarungen gelöscht**. "
        "Die Teilnehmerliste bleibt erhalten."
    )
    saved = st.checkbox("Ja, alle Daten wurden gesichert (CSV/HTML/PDF-Export).")
    again = st.checkbox("Ich bestätige erneut: Turnier jetzt abschließen.")
    abbrechen, speichern = st.columns(2)
    with abbrechen:
        if st.button("Abbrechen", width="stretch"):
            st.rerun()
    with speichern:
        if st.button("Endgültig abschließen", type="primary", width="stretch", disabled=not (saved and again)):
            finish_tournament()
            st.session_state.view_round = 0
            st.session_state.flash_success = "Turnier abgeschlossen. Rundenergebnisse wurden gelöscht."
            st.rerun()


@st.dialog("Teilnehmerliste löschen")
def delete_all_players_dialog() -> None:
    st.write("Die **gesamte Teilnehmerliste** wird gelöscht.")
    confirmed = st.checkbox("Ich bestätige das Löschen der gesamten Teilnehmerliste.")
    abbrechen, speichern = st.columns(2)
    with abbrechen:
        if st.button("Abbrechen", width="stretch"):
            st.rerun()
    with speichern:
        if st.button("Liste löschen", type="primary", width="stretch", disabled=not confirmed):
            error = delete_all_players()
            if error:
                st.error(error)
            else:
                st.session_state.flash_success = "Teilnehmerliste wurde gelöscht."
                st.rerun()


def export_buttons(prefix: str, title: str, headers, rows) -> None:
    csv_data = to_csv(headers, rows)
    html_data = to_html(title, headers, rows)
    pdf_data = to_pdf(title, headers, rows)
    col1, col2, col3 = st.columns(3)
    col1.download_button("CSV", csv_data, file_name=f"{prefix}.csv", mime="text/csv", key=f"{prefix}_csv")
    col2.download_button("HTML", html_data, file_name=f"{prefix}.html", mime="text/html", key=f"{prefix}_html")
    col3.download_button(
        "PDF", pdf_data, file_name=f"{prefix}.pdf", mime="application/pdf", key=f"{prefix}_pdf"
    )


def import_players_from_csv(uploaded) -> str:
    raw = uploaded.getvalue()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if not rows:
        return "Die CSV-Datei ist leer."
    header = [cell.strip() for cell in rows[0]]
    if header != PLAYER_CSV_HEADERS:
        return (
            "Ungültiges CSV-Format. Erwartet werden die Spalten: "
            + ";".join(PLAYER_CSV_HEADERS)
        )
    added = 0
    for row in rows[1:]:
        if len(row) < 6:
            continue
        _id, vorname, nachname, verein, dwz_raw, status = [c.strip() for c in row[:6]]
        if not vorname:
            continue
        dwz_value, dwz_error = parse_dwz(dwz_raw)
        if dwz_error:
            return f"Ungültige DWZ bei {vorname} {nachname}: {dwz_error}"
        add_player(vorname, nachname, verein, dwz_value, active=(status.lower() != "inaktiv"))
        added += 1
    return f"{added} Teilnehmer importiert." if added else "Keine Teilnehmerzeilen gefunden."


def page_participants():
    st.subheader("Teilnehmererfassung")
    st.markdown("#### DSB-Wertungsportal")
    st.caption("Standard-Erfassung: Spieler suchen und zum Turnier übernehmen.")
    c1, c2, c3 = st.columns(3)
    s_vn = c1.text_input("Vorname", key="dsb_vn")
    s_nn = c2.text_input("Nachname", key="dsb_nn")
    s_vkz = c3.text_input("VKZ optional", key="dsb_vkz")
    if st.button("Im DSB suchen"):
        if not s_vn.strip() and not s_nn.strip() and not s_vkz.strip():
            st.error("Bitte mindestens Nachname, Vorname oder VKZ angeben.")
        else:
            results, error = search_players(s_vn, s_nn, s_vkz)
            st.session_state.dsb_results = results
            st.session_state.dsb_error = error
    if st.session_state.get("dsb_error"):
        st.warning(st.session_state.dsb_error)
    for index, hit in enumerate(st.session_state.get("dsb_results") or []):
        label = f"{hit['vorname']} {hit['nachname']} · {hit['verein']} · DWZ {hit['dwz']}"
        if st.button(f"Zum Turnier hinzufügen: {label}", key=f"dsb_add_{index}"):
            add_player(
                hit["vorname"] or "Unbekannt",
                hit["nachname"],
                hit["verein"],
                int(hit["dwz"] or 0),
                hit.get("dsb_id"),
            )
            st.session_state.flash_success = f"{label} wurde hinzugefügt."
            st.session_state.clear_dsb_form = True
            st.rerun()

    with st.expander("Manuell erfassen (Personendaten)"):
        with st.form("player_form", clear_on_submit=False):
            row1_col1, row1_col2 = st.columns(2)
            vorname = row1_col1.text_input("Vorname *", key="player_vorname")
            nachname = row1_col2.text_input("Nachname", key="player_nachname")
            row2_col1, row2_col2 = st.columns(2)
            verein = row2_col1.text_input("Verein", key="player_verein")
            dwz_raw = row2_col2.text_input("DWZ", key="player_dwz")
            submitted = st.form_submit_button("Hinzufügen")

        if submitted:
            vorname = vorname.strip()
            nachname = nachname.strip()
            verein = verein.strip()
            dwz_value, dwz_error = parse_dwz(dwz_raw)
            if not vorname:
                st.error("Bitte den Vornamen ausfüllen. Die übrigen Eingaben bleiben erhalten.")
            if dwz_error:
                st.error(dwz_error)
            if vorname and dwz_error is None:
                add_player(vorname, nachname, verein, dwz_value)
                st.session_state.flash_success = (
                    f"{player_display_name(vorname, nachname)} wurde hinzugefügt."
                )
                st.session_state.clear_player_form = True
                st.rerun()

    st.divider()
    st.subheader("Teilnehmer")
    list_actions = st.columns(2)
    with list_actions[0]:
        uploaded = st.file_uploader("Teilnehmerliste importieren (CSV)", type=["csv"])
        if uploaded is not None and st.button("CSV importieren"):
            st.session_state.flash_success = import_players_from_csv(uploaded)
            st.rerun()
    with list_actions[1]:
        if st.button("Gesamte Teilnehmerliste löschen"):
            delete_all_players_dialog()

    current_players = load_players()
    if not current_players:
        st.info("Noch keine Teilnehmer erfasst.")
        return

    header = st.columns([0.4, 1.1, 1.1, 1.2, 0.6, 0.7, 1.3])
    for col, label in zip(header, ["ID", "Vorname", "Nachname", "Verein", "DWZ", "Status", "Aktionen"]):
        col.markdown(f"**{label}**")

    for player in current_players:
        player_id = int(player["id"])
        name = player_display_name(player["vorname"], player["nachname"])
        cols = st.columns([0.4, 1.1, 1.1, 1.2, 0.6, 0.7, 1.3], vertical_alignment="center")
        cols[0].write(str(player_id))
        cols[1].write(player["vorname"])
        cols[2].write(player["nachname"])
        cols[3].write(player["verein"])
        cols[4].write(str(player["dwz"]))
        cols[5].write("aktiv" if player["active"] else "inaktiv")
        a1, a2, a3, a4 = cols[6].columns(4)
        if a1.button("✏️", key=f"edit_{player_id}", help="Teilnehmer bearbeiten"):
            edit_player_dialog(player_id)
        can_delete = settings["status"] == "setup" and not player_has_games(player_id)
        if a2.button("🗑️", key=f"delete_{player_id}", help="Teilnehmer löschen", disabled=not can_delete):
            confirm_delete_dialog(player_id, name)
        if player["active"]:
            if a3.button("⏸️", key=f"off_{player_id}", help="Inaktiv setzen"):
                set_player_active(player_id, False)
                st.rerun()
        else:
            if a3.button("▶️", key=f"on_{player_id}", help="Aktiv setzen"):
                set_player_active(player_id, True)
                st.rerun()

    rows = [
        [p["id"], p["vorname"], p["nachname"], p["verein"], p["dwz"], "aktiv" if p["active"] else "inaktiv"]
        for p in current_players
    ]
    export_buttons("teilnehmer", "Teilnehmer", PLAYER_CSV_HEADERS, rows)
    st.caption(f"{len(current_players)} Teilnehmer in der Datenbank.")


def _on_tb1_change():
    tb1, tb2, tb3 = cascade_tiebreaks(
        st.session_state.config_tb1,
        st.session_state.get("config_tb2", TIEBREAK_NONE),
        st.session_state.get("config_tb3", TIEBREAK_NONE),
    )
    st.session_state.config_tb2 = tb2
    st.session_state.config_tb3 = tb3


def _on_tb2_change():
    tb1, tb2, tb3 = cascade_tiebreaks(
        st.session_state.get("config_tb1", TIEBREAK_NONE),
        st.session_state.config_tb2,
        st.session_state.get("config_tb3", TIEBREAK_NONE),
    )
    st.session_state.config_tb3 = tb3


def page_config():
    st.subheader("Turnier konfigurieren")
    locked = settings["status"] != "setup"
    if locked:
        st.info("Die Konfiguration ist nach Turnierstart fest (FIDE: Rundenzahl vorab).")

    tournament_type = st.radio(
        "Turnierart",
        ["swiss", "round_robin"],
        format_func=lambda v: "Schweizer System" if v == "swiss" else "Rundensystem",
        index=0 if settings["tournament_type"] == "swiss" else 1,
        disabled=locked,
        horizontal=True,
    )
    rounds = st.text_input(
        "Anzahl Runden (nur Schweizer System)",
        value=str(settings["rounds"]),
        disabled=locked or tournament_type != "swiss",
    )
    if tournament_type == "round_robin":
        st.caption(
            f"Rundensystem: {planned_rounds({**settings, 'tournament_type': 'round_robin'})} "
            "Runden bei den aktuellen aktiven Teilnehmern."
        )

    st.markdown("Feinwertung (Reihenfolge nach Punkten)")
    tb_keys = list(TIEBREAK_OPTIONS.keys())
    if "config_tb1" not in st.session_state:
        st.session_state.config_tb1 = settings["tiebreak1"] if settings["tiebreak1"] in TIEBREAK_OPTIONS else "buchholz"
        st.session_state.config_tb2 = settings["tiebreak2"] if settings["tiebreak2"] in TIEBREAK_OPTIONS else "direct"
        st.session_state.config_tb3 = settings["tiebreak3"] if settings["tiebreak3"] in TIEBREAK_OPTIONS else "wins"
        st.session_state.config_tb1, st.session_state.config_tb2, st.session_state.config_tb3 = cascade_tiebreaks(
            st.session_state.config_tb1,
            st.session_state.config_tb2,
            st.session_state.config_tb3,
        )

    tb1 = st.selectbox(
        "Feinwertung 1",
        tb_keys,
        format_func=lambda k: TIEBREAK_OPTIONS[k],
        key="config_tb1",
        disabled=locked,
        on_change=_on_tb1_change,
    )
    tb2 = st.selectbox(
        "Feinwertung 2",
        tb_keys,
        format_func=lambda k: TIEBREAK_OPTIONS[k],
        key="config_tb2",
        disabled=locked or tb1 == TIEBREAK_NONE,
        on_change=_on_tb2_change,
    )
    tb3 = st.selectbox(
        "Feinwertung 3",
        tb_keys,
        format_func=lambda k: TIEBREAK_OPTIONS[k],
        key="config_tb3",
        disabled=locked or tb1 == TIEBREAK_NONE or tb2 == TIEBREAK_NONE,
    )
    if not locked and st.button("Konfiguration speichern"):
        if tournament_type == "swiss":
            if not rounds.strip().isdigit() or int(rounds) < 1:
                st.error("Anzahl Runden muss eine ganze Zahl ≥ 1 sein.")
                return
            round_count = int(rounds)
        else:
            round_count = planned_rounds({**settings, "tournament_type": "round_robin"})
        tb1, tb2, tb3 = cascade_tiebreaks(tb1, tb2, tb3)
        save_settings(tournament_type, round_count, tb1, tb2, tb3)
        st.success("Konfiguration gespeichert.")
        st.rerun()


def page_tournament():
    st.subheader("Turnierverwaltung")
    total = planned_rounds(settings)
    st.write(
        f"Status: **{settings['status']}** · "
        f"Modus: **{'Schweizer System' if settings['tournament_type'] == 'swiss' else 'Rundensystem'}** · "
        f"Runde {settings['current_round']} von {total}"
    )
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    if c1.button("Turnier starten", disabled=settings["status"] != "setup"):
        error = start_tournament()
        st.session_state.flash_error = error
        if not error:
            st.session_state.flash_success = "Turnier gestartet. TPN nach DWZ vergeben."
        st.rerun()
    if c2.button("Runde starten", disabled=settings["status"] != "running"):
        error = start_round()
        st.session_state.flash_error = error
        if not error:
            st.session_state.flash_success = f"Runde {get_settings()['current_round']} gestartet."
            st.session_state.view_round = get_settings()["current_round"]
        st.rerun()
    if c3.button("Paarungen ermitteln", disabled=settings["status"] not in ("running", "finished")):
        error = generate_pairings()
        st.session_state.flash_error = error
        if not error:
            st.session_state.flash_success = "Paarungen ermittelt."
        st.rerun()
    if c4.button("Runde abschließen und nächste ermitteln", disabled=settings["status"] != "running"):
        error = close_and_next()
        st.session_state.flash_error = error
        if not error:
            st.session_state.flash_success = (
                "Runde abgeschlossen, nächste Paarung ermittelt (falls weitere Runde)."
            )
            st.session_state.view_round = get_settings()["current_round"]
        st.rerun()
    if c5.button("Runde abbrechen", disabled=settings["status"] != "running"):
        error = abort_round()
        st.session_state.flash_error = error
        if not error:
            st.session_state.flash_success = "Runde zurückgesetzt."
        st.rerun()
    if c6.button("Turnier abschließen", disabled=settings["status"] == "setup"):
        finish_tournament_dialog()

    live_games = load_games()
    round_numbers = sorted({g["round_number"] for g in live_games})
    if not round_numbers:
        st.info("Keine Paarungen für die aktuelle Runde.")
        return

    if st.session_state.get("view_round") not in round_numbers:
        st.session_state.view_round = round_numbers[-1]
    view_round = st.session_state.view_round
    idx = round_numbers.index(view_round)
    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("◀ Runde zurück", disabled=idx <= 0):
            st.session_state.view_round = round_numbers[idx - 1]
            st.rerun()
    with nav2:
        st.markdown(f"### Paarungen Runde {view_round} von {total}")
    with nav3:
        if st.button("Runde vor ▶", disabled=idx >= len(round_numbers) - 1):
            st.session_state.view_round = round_numbers[idx + 1]
            st.rerun()

    current = [g for g in live_games if g["round_number"] == view_round]
    live_players = load_players()
    scores = score_map_before(live_players, live_games, view_round)
    historic = view_round != settings["current_round"] or settings["status"] != "running"
    headers = ["Brett", "Weiß", "Punkte Weiß", "Schwarz", "Punkte Schwarz", "Ergebnis"]
    rows = []
    for game in current:
        white = name_by_id(live_players, game["white_id"])
        white_label = name_with_score(live_players, game["white_id"], scores)
        if game["is_bye"]:
            st.write(f"Brett {game['board']}: **{white_label}** — Freilos (1 Punkt)")
            rows.append([game["board"], white, format_points(scores.get(game["white_id"], 0)), "Freilos", "", "1-0"])
            continue
        black = name_by_id(live_players, game["black_id"])
        black_label = name_with_score(live_players, game["black_id"], scores)
        options = ["1-0", "1/2-1/2", "0-1"]
        current_result = game["result"] if game["result"] in options else None
        result = st.selectbox(
            f"Brett {game['board']}: {white_label} – {black_label}",
            options,
            index=None if current_result is None else options.index(current_result),
            placeholder="Ergebnis wählen",
            key=f"res_{game['id']}",
            disabled=settings["status"] == "setup",
        )
        if result and result != game["result"]:
            if historic and game["result"]:
                confirm_result_change_dialog(
                    game["id"],
                    game["result"],
                    result,
                    f"{white} – {black}",
                )
            else:
                set_game_result(game["id"], result)
                st.rerun()
        rows.append(
            [
                game["board"],
                white,
                format_points(scores.get(game["white_id"], 0)),
                black,
                format_points(scores.get(game["black_id"], 0)),
                game["result"] or "",
            ]
        )
    export_buttons("paarungen", f"Paarungen Runde {view_round}", headers, rows)


def _completed_round_label() -> tuple:
    total = planned_rounds(settings)
    completed = [r for r in load_rounds() if r["status"] == "completed"]
    shown = max((r["number"] for r in completed), default=0)
    return shown, total


def page_standings():
    st.subheader("Rangliste")
    shown, total = _completed_round_label()
    st.caption(f"Nach Runde {shown} von {total}")
    tb_headers = [TIEBREAK_OPTIONS[k] for k in tiebreaks]
    rows_data = ranked_standings(load_players(), load_games(), tiebreaks)
    headers = ["Rang", "TPN", "Name", "Verein", "DWZ", "Punkte"] + tb_headers + ["Status"]
    rows = []
    for row in rows_data:
        cells = [
            row["rank"],
            row.get("tpn") or "",
            player_display_name(row["vorname"], row["nachname"]),
            row["verein"],
            row["dwz"],
            row["score"],
        ]
        for tb in tiebreaks:
            if tb == "buchholz":
                cells.append(row["buchholz"])
            elif tb == "wins":
                cells.append(row["wins"])
            elif tb == "direct":
                cells.append(row.get("played_points", ""))
            else:
                cells.append("")
        cells.append("aktiv" if row["active"] else "inaktiv")
        rows.append(cells)
    st.dataframe(pd.DataFrame(rows, columns=headers), hide_index=True, width="stretch")
    export_buttons("rangliste", "Rangliste", headers, rows)


def page_crosstable():
    st.subheader("Kreuztabelle")
    shown, total = _completed_round_label()
    st.caption(f"Nach Runde {shown} von {total}")
    live_players = load_players()
    live_games = load_games()
    standings = ranked_standings(live_players, live_games, tiebreaks)
    names = {p["id"]: player_display_name(p["vorname"], p["nachname"]) for p in live_players}
    ids = [row["id"] for row in standings]
    matrix = {a: {b: "" for b in ids} for a in ids}
    for game in live_games:
        if game.get("is_bye") or not game.get("result"):
            continue
        white_id, black_id = game["white_id"], game["black_id"]
        if white_id not in matrix or black_id not in matrix:
            continue
        result = game["result"]
        if result == "1-0":
            matrix[white_id][black_id] = "1"
            matrix[black_id][white_id] = "0"
        elif result == "0-1":
            matrix[white_id][black_id] = "0"
            matrix[black_id][white_id] = "1"
        elif result == "1/2-1/2":
            matrix[white_id][black_id] = "½"
            matrix[black_id][white_id] = "½"
    headers = ["Rang", "Name", "Pkt"] + [str(i + 1) for i in range(len(ids))]
    rows = []
    table = []
    for row in standings:
        cells = [row["rank"], names[row["id"]], row["score"]]
        for other in ids:
            cells.append("·" if other == row["id"] else matrix[row["id"]].get(other, ""))
        rows.append(cells)
        table.append(cells)
    st.dataframe(pd.DataFrame(table, columns=headers), hide_index=True, width="stretch")
    export_buttons("kreuztabelle", "Kreuztabelle", headers, rows)


def page_progress():
    st.subheader("Fortschrittstabelle")
    shown, total = _completed_round_label()
    st.caption(f"Nach Runde {shown} von {total}")
    live_players = load_players()
    live_games = load_games()
    data, round_numbers = progress_rows(live_players, live_games, tiebreaks)
    headers = ["Rang", "Name"] + [f"R{n}" for n in round_numbers] + ["Punkte"]
    rows = []
    for row in data:
        cells = [row["rank"], row["name"]]
        for number in round_numbers:
            cells.append(row["rounds"].get(number, "–"))
        cells.append(row["score"])
        rows.append(cells)
    if rows:
        st.dataframe(pd.DataFrame(rows, columns=headers), hide_index=True, width="stretch")
        export_buttons("fortschritt", "Fortschrittstabelle", headers, rows)
    else:
        st.info("Noch keine Rundenergebnisse für die Fortschrittstabelle.")


st.title("♟️ Schachturnier")
if flash_success := st.session_state.pop("flash_success", None):
    st.success(flash_success)
if flash_error := st.session_state.pop("flash_error", None):
    if flash_error:
        st.error(flash_error)

page = st.sidebar.radio(
    "Bereich",
    ["Teilnehmer", "Konfiguration", "Turnier", "Rangliste", "Kreuztabelle", "Fortschritt"],
)
if page == "Teilnehmer":
    page_participants()
elif page == "Konfiguration":
    page_config()
elif page == "Turnier":
    page_tournament()
elif page == "Rangliste":
    page_standings()
elif page == "Kreuztabelle":
    page_crosstable()
else:
    page_progress()
