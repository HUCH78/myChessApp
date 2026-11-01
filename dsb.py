import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

LIVE_PERSONS = "https://schachde-apps.liga.nu/dsbwertungsportal/rs/dwz/dwzliste/persons"
DEMO_PERSONS = "https://schachde-appsdemo.liga.nu/dsbwertungsportal/rs/dwz/dwzliste/persons"
DEWIS_CLUB_XML = "https://www.schachbund.de/php/dewis/verein.php"


def _get(url: str, timeout: int = 12):
    request = urllib.request.Request(url, headers={"Accept": "application/json, application/xml, text/xml"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def _parse_rest_persons(payload: bytes):
    data = json.loads(payload.decode("utf-8"))
    items = data.get("items") or data.get("content") or data.get("data") or []
    if isinstance(data, list):
        items = data
    results = []
    for item in items:
        memberships = item.get("memberships") or []
        membership = memberships[0] if memberships else {}
        dwz = item.get("dwz") or item.get("rating") or 0
        try:
            dwz = int(dwz)
        except (TypeError, ValueError):
            dwz = 0
        results.append(
            {
                "dsb_id": str(item.get("nuLigaId") or item.get("id") or item.get("dsbId") or ""),
                "vorname": item.get("firstname") or item.get("firstName") or "",
                "nachname": item.get("lastname") or item.get("lastName") or "",
                "verein": membership.get("clubName") or item.get("clubName") or "",
                "dwz": dwz,
            }
        )
    return results


def _parse_dewis_xml(payload: bytes, vorname: str, nachname: str):
    root = ET.fromstring(payload)
    vn = (vorname or "").strip().lower()
    nn = (nachname or "").strip().lower()
    results = []
    for spieler in root.iter():
        tag = spieler.tag.lower()
        if "spieler" not in tag:
            continue
        first = ""
        last = ""
        club = ""
        dwz = 0
        dsb_id = ""
        for child in list(spieler) + [spieler]:
            name = child.tag.lower()
            text = (child.text or "").strip()
            if name in ("vorname", "vname"):
                first = text
            elif name in ("nachname", "nname", "name"):
                last = text
            elif name in ("verein", "zpsverein"):
                club = text
            elif name == "dwz":
                dwz = int(text) if text.isdigit() else 0
            elif name in ("pkz", "id"):
                dsb_id = text
        attrs = spieler.attrib
        first = first or attrs.get("vorname", "")
        last = last or attrs.get("nachname", "") or attrs.get("name", "")
        club = club or attrs.get("verein", "")
        if attrs.get("dwz", "").isdigit():
            dwz = int(attrs["dwz"])
        dsb_id = dsb_id or attrs.get("pkz", "")
        if nn and nn not in last.lower():
            continue
        if vn and vn not in first.lower():
            continue
        if last or first:
            results.append(
                {
                    "dsb_id": dsb_id,
                    "vorname": first,
                    "nachname": last,
                    "verein": club,
                    "dwz": dwz,
                }
            )
    return results


def search_players(vorname: str, nachname: str, vkz: str = ""):
    params = {"limit": "25"}
    if vorname.strip():
        params["firstname"] = vorname.strip()
    if nachname.strip():
        params["lastname"] = nachname.strip()
    if vkz.strip():
        params["vkz"] = vkz.strip()
    query = urllib.parse.urlencode(params)
    errors = []
    for base in (LIVE_PERSONS, DEMO_PERSONS):
        try:
            payload, _ctype = _get(f"{base}?{query}")
            results = _parse_rest_persons(payload)
            if results:
                return results, None
        except urllib.error.HTTPError as exc:
            errors.append(f"{base}: HTTP {exc.code}")
        except Exception as exc:
            errors.append(f"{base}: {exc}")

    if vkz.strip():
        club_query = urllib.parse.urlencode({"zps": vkz.strip(), "format": "xml"})
        try:
            payload, _ctype = _get(f"{DEWIS_CLUB_XML}?{club_query}")
            results = _parse_dewis_xml(payload, vorname, nachname)
            return results, None
        except Exception as exc:
            errors.append(f"DeWIS XML: {exc}")

    message = (
        "DSB-Suche nicht erreichbar. "
        "Das Wertungsportal (REST/XML) kann Anmeldung verlangen. "
        + " ".join(errors[-3:])
    )
    return [], message
