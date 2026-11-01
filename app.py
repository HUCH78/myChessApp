import pandas as pd
import streamlit as st

from db import (
    TIEBREAK_OPTIONS,
    add_player,
    delete_player,
    get_player,
    get_settings,
    init_db,
    load_games,
    load_players,
    player_has_games,
    save_settings,
    set_game_result,
    set_player_active,
    update_player,
)
from dsb import search_players
from export_views import to_csv, to_html, to_pdf
from standings import ranked_standings
from tournament import (
    abort_round,
    close_and_next,
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


FORM_KEYS = ("player_vorname", "player_nachname", "player_verein", "player_dwz")


def reset_player_form_state() -> None:
    for key in FORM_KEYS:
        st.session_state.pop(key, None)


st.set_page_config(page_title="Schachturnier", page_icon="♟️", layout="wide")
init_db()

if st.session_state.pop("clear_player_form", False):
    reset_player_form_state()

settings = get_settings()
players = load_players()
games = load_games()
tiebreaks = [settings["tiebreak1"], settings["tiebreak2"], settings["tiebreak3"]]


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


def page_participants():
    st.subheader("Teilnehmererfassung")
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
            st.session_state.flash_success = f"{player_display_name(vorname, nachname)} wurde hinzugefügt."
            st.session_state.clear_player_form = True
            st.rerun()

    with st.expander("Spieler über DSB-Wertungsportal suchen"):
        st.caption(
            "Suche über die Schnittstelle des DSB-Wertungsportals "
            "(REST-Personenliste, ergänzend DeWIS-XML der Vereinsliste)."
        )
        c1, c2, c3 = st.columns(3)
        s_vn = c1.text_input("Vorname (Suche)", key="dsb_vn")
        s_nn = c2.text_input("Nachname (Suche)", key="dsb_nn")
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
                add_player(hit["vorname"] or "Unbekannt", hit["nachname"], hit["verein"], int(hit["dwz"] or 0), hit.get("dsb_id"))
                st.session_state.flash_success = f"{label} wurde hinzugefügt."
                st.rerun()

    st.divider()
    st.subheader("Teilnehmer")
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
    export_buttons(
        "teilnehmer",
        "Teilnehmer",
        ["ID", "Vorname", "Nachname", "Verein", "DWZ", "Status"],
        rows,
    )
    st.caption(f"{len(current_players)} Teilnehmer in der Datenbank.")


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
        st.caption(f"Rundensystem: {planned_rounds({**settings, 'tournament_type': 'round_robin'})} Runden bei den aktuellen aktiven Teilnehmern.")

    st.markdown("Feinwertung (Reihenfolge nach Punkten)")
    tb1 = st.selectbox(
        "Feinwertung 1",
        list(TIEBREAK_OPTIONS.keys()),
        format_func=lambda k: TIEBREAK_OPTIONS[k],
        index=list(TIEBREAK_OPTIONS).index(settings["tiebreak1"]),
        disabled=locked,
    )
    tb2 = st.selectbox(
        "Feinwertung 2",
        list(TIEBREAK_OPTIONS.keys()),
        format_func=lambda k: TIEBREAK_OPTIONS[k],
        index=list(TIEBREAK_OPTIONS).index(settings["tiebreak2"]),
        disabled=locked,
    )
    tb3 = st.selectbox(
        "Feinwertung 3",
        list(TIEBREAK_OPTIONS.keys()),
        format_func=lambda k: TIEBREAK_OPTIONS[k],
        index=list(TIEBREAK_OPTIONS).index(settings["tiebreak3"]),
        disabled=locked,
    )
    if not locked and st.button("Konfiguration speichern"):
        if tournament_type == "swiss":
            if not rounds.strip().isdigit() or int(rounds) < 1:
                st.error("Anzahl Runden muss eine ganze Zahl ≥ 1 sein.")
                return
            round_count = int(rounds)
        else:
            round_count = planned_rounds({**settings, "tournament_type": "round_robin"})
        save_settings(tournament_type, round_count, tb1, tb2, tb3)
        st.success("Konfiguration gespeichert.")
        st.rerun()


def page_tournament():
    st.subheader("Turnierverwaltung")
    st.write(
        f"Status: **{settings['status']}** · "
        f"Modus: **{'Schweizer System' if settings['tournament_type'] == 'swiss' else 'Rundensystem'}** · "
        f"Runde {settings['current_round']} von {planned_rounds(settings)}"
    )
    c1, c2, c3, c4, c5 = st.columns(5)
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
            st.session_state.flash_success = "Runde abgeschlossen, nächste Paarung ermittelt (falls weitere Runde)."
        st.rerun()
    if c5.button("Runde abbrechen", disabled=settings["status"] != "running"):
        error = abort_round()
        st.session_state.flash_error = error
        if not error:
            st.session_state.flash_success = "Runde zurückgesetzt."
        st.rerun()

    current = [g for g in load_games() if g["round_number"] == settings["current_round"]]
    if not current:
        st.info("Keine Paarungen für die aktuelle Runde.")
        return

    st.markdown(f"### Paarungen Runde {settings['current_round']}")
    live_players = load_players()
    headers = ["Brett", "Weiß", "Schwarz", "Ergebnis"]
    rows = []
    for game in current:
        white = name_by_id(live_players, game["white_id"])
        black = "—" if game["is_bye"] else name_by_id(live_players, game["black_id"])
        if game["is_bye"]:
            st.write(f"Brett {game['board']}: **{white}** — Freilos (1 Punkt)")
            rows.append([game["board"], white, "Freilos", "1-0"])
            continue
        options = ["1-0", "1/2-1/2", "0-1"]
        current_result = game["result"] if game["result"] in options else None
        result = st.selectbox(
            f"Brett {game['board']}: {white} – {black}",
            options,
            index=None if current_result is None else options.index(current_result),
            placeholder="Ergebnis wählen",
            key=f"res_{game['id']}",
            disabled=game["result"] is not None and get_settings()["status"] == "finished",
        )
        if result and result != game["result"]:
            set_game_result(game["id"], result)
            st.rerun()
        rows.append([game["board"], white, black, game["result"] or ""])
    export_buttons("paarungen", f"Paarungen Runde {settings['current_round']}", headers, rows)


def page_standings():
    st.subheader("Rangliste")
    rows_data = ranked_standings(load_players(), load_games(), tiebreaks)
    headers = ["Rang", "TPN", "Name", "Verein", "DWZ", "Punkte", "Buchholz", "Siege", "Status"]
    rows = []
    for row in rows_data:
        rows.append(
            [
                row["rank"],
                row.get("tpn") or "",
                player_display_name(row["vorname"], row["nachname"]),
                row["verein"],
                row["dwz"],
                row["score"],
                row["buchholz"],
                row["wins"],
                "aktiv" if row["active"] else "inaktiv",
            ]
        )
    st.dataframe(pd.DataFrame(rows, columns=headers), hide_index=True, width="stretch")
    export_buttons("rangliste", "Rangliste", headers, rows)


def page_crosstable():
    st.subheader("Kreuztabelle")
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
    for index, row in enumerate(standings):
        cells = [row["rank"], names[row["id"]], row["score"]]
        for other in ids:
            cells.append("·" if other == row["id"] else matrix[row["id"]].get(other, ""))
        rows.append(cells)
        table.append(cells)
    st.dataframe(pd.DataFrame(table, columns=headers), hide_index=True, width="stretch")
    export_buttons("kreuztabelle", "Kreuztabelle", headers, rows)


st.title("♟️ Schachturnier")
if flash_success := st.session_state.pop("flash_success", None):
    st.success(flash_success)
if flash_error := st.session_state.pop("flash_error", None):
    if flash_error:
        st.error(flash_error)

page = st.sidebar.radio(
    "Bereich",
    ["Teilnehmer", "Konfiguration", "Turnier", "Rangliste", "Kreuztabelle"],
)
if page == "Teilnehmer":
    page_participants()
elif page == "Konfiguration":
    page_config()
elif page == "Turnier":
    page_tournament()
elif page == "Rangliste":
    page_standings()
else:
    page_crosstable()
