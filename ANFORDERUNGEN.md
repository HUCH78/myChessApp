# Fachliche Anforderungen — Schachturnier

Diese Datei ist die **Quelle der Wahrheit** für das, was die App können soll.
Anforderungen sind hierarchisch nummeriert (z. B. `1.2.3.1`). In Cursor kannst du sagen:
„Setze `2.1.4` um.“

Status je Anforderung:

- **Umgesetzt** — ist in der App vorhanden
- **Geplant** — noch nicht gebaut

Neue Wünsche unter der nächsten freien Nummer ergänzen.

---

## 1 Ziel

**1.1** Lokale Streamlit-App zur Verwaltung eines Schachturniers. — *Umgesetzt*

**1.2** Datenhaltung in der SQLite-Datei `chess.db`. — *Umgesetzt*

---

## 2 Teilnehmer

### 2.1 Erfassung

**2.1.1** Teilnehmer können erfasst werden. — *Umgesetzt*

**2.1.1.1** Vorname — einzige Pflichtangabe. — *Umgesetzt*

**2.1.1.2** Nachname — optional. — *Umgesetzt*

**2.1.1.3** Verein — optional. — *Umgesetzt*

**2.1.1.4** DWZ als einfache ganze Zahl zwischen 0 und 3000 — optional, ohne Plus-/Minus-Schalter. — *Umgesetzt*

**2.1.2** Button **Hinzufügen** speichert den Teilnehmer in der Tabelle `players`. — *Umgesetzt*

**2.1.3** Cursor-/Tab-Reihenfolge der Felder: Vorname, Nachname, Verein, DWZ. — *Umgesetzt*

**2.1.4** Fehlt ein Pflichtfeld, erscheint eine Fehlermeldung. Bereits eingegebene Werte bleiben im Formular stehen. — *Umgesetzt*

**2.1.5** Zusätzlich können Spieler über die Schnittstelle des DSB-Wertungsportals gesucht und zum Turnier hinzugefügt werden. — *Umgesetzt*

### 2.2 Übersicht

**2.2.1** Unter dem Formular erscheint eine Tabelle aller Teilnehmer aus der Datenbank. — *Umgesetzt*

**2.2.2** Die Liste aktualisiert sich nach dem Speichern. — *Umgesetzt*

**2.2.3** In der Übersichtstabelle kann ein Teilnehmer gelöscht werden. — *Umgesetzt*

**2.2.4** Das Löschen muss bestätigt werden. — *Umgesetzt*

**2.2.5** Verfügbare Aktionen stehen rechts in der Spalte **Aktionen** als Icons. — *Umgesetzt*

**2.2.5.1** Teilnehmer löschen. — *Umgesetzt*

**2.2.5.2** Teilnehmer bearbeiten. — *Umgesetzt*

**2.2.6** Es gibt keine linke Spalte zum Selektieren einzelner Teilnehmer. — *Umgesetzt*

**2.2.7** Teilnehmer können inaktiv gesetzt werden und nehmen dann nicht mehr am Turnier teil. — *Umgesetzt*

**2.2.8** Teilnehmer können wieder aktiv gesetzt werden. — *Umgesetzt*

---

## 3 Turnier konfigurieren

**3.1** Turnierart kann gewählt werden. — *Umgesetzt*

**3.1.1** Schweizer System. — *Umgesetzt*

**3.1.2** Rundensystem. — *Umgesetzt*

**3.2** Beim Schweizer System wird die Anzahl der Runden vorab festgelegt (FIDE C.04.1 Art. 1). — *Umgesetzt*

**3.3** Feinwertung nach Punkten, wählbar und reihenfolgefest. — *Umgesetzt*

**3.3.1** Buchholz. — *Umgesetzt*

**3.3.2** Direkter Vergleich. — *Umgesetzt*

**3.3.3** Anzahl Siege. — *Umgesetzt*

---

## 4 Turnierverwaltung

**4.1** Turniere können nach Schweizer System und Rundensystem durchgeführt werden. — *Umgesetzt*

**4.2** Paarung und Ablauf richten sich nach den FIDE-Vorgaben C.04.1 (Basic Rules for Swiss Systems, wirksam 1. Februar 2026) und C.04.2 (General Handling Rules for Swiss Tournaments). — *Umgesetzt*

**4.2.1** Keine Wiederholungspartien. — *Umgesetzt*

**4.2.2** Ungerade Teilnehmerzahl: Pairing-Allocated Bye mit Gewinnpunkt, ohne Farbe; kein zweites Vollpunkt-Freilos. — *Umgesetzt*

**4.2.3** Paarung möglichst in derselben Punktegruppe; Farbvorlieben nach Weiß-/Schwarz-Differenz und letzter Farbe. — *Umgesetzt*

**4.2.4** Initiale Reihenfolge / TPN nach Stärke (DWZ), dann Name. — *Umgesetzt*

**4.2.5** Zurückgetretene bzw. inaktive Teilnehmer werden nicht gepaart. — *Umgesetzt*

**4.3** Funktionen des Turnierablaufs. — *Umgesetzt*

**4.3.1** Turnier starten. — *Umgesetzt*

**4.3.2** Runde starten. — *Umgesetzt*

**4.3.3** Paarungen ermitteln. — *Umgesetzt*

**4.3.4** Ergebnisse einer Runde eingeben. — *Umgesetzt*

**4.3.5** Runde abschließen und nächste Runde ermitteln. — *Umgesetzt*

**4.3.6** Runde abbrechen und Zustand vor Beginn der Runde zurücksetzen. — *Umgesetzt*

**4.3.7** Rangliste anzeigen inkl. Punkte und Feinwertung. — *Umgesetzt*

**4.3.8** Kreuztabelle anzeigen. — *Umgesetzt*

**4.4** Jede Ansicht (Teilnehmer, Paarungen, Rangliste, Kreuztabelle) kann als HTML, PDF und CSV exportiert werden. — *Umgesetzt*

---

## 5 Offene Wünsche

Hier die nächste freie Nummer vergeben.
