"""Importierte Daten mit den eigenen zusammenführen."""

from __future__ import annotations

import copy

from .model import Daten


def konflikte_finden(meine: Daten, import_: Daten) -> list[dict]:
    konflikte = []
    for jahr, s_imp in sorted(import_.saisons.items()):
        s_mein = meine.saisons.get(jahr)
        if s_mein is None:
            continue
        if s_mein.start != s_imp.start:
            konflikte.append(
                {
                    "id": f"start:{jahr}",
                    "jahr": jahr,
                    "art": "start",
                    "datum": None,
                    "mein": s_mein.start.isoformat(),
                    "import": s_imp.start.isoformat(),
                }
            )
        for tag in sorted(s_imp.eintraege):
            mein = s_mein.eintraege.get(tag)
            imp = s_imp.eintraege[tag]
            if mein is not None and mein != imp:
                konflikte.append(
                    {
                        "id": f"betrag:{tag.isoformat()}",
                        "jahr": jahr,
                        "art": "betrag",
                        "datum": tag.isoformat(),
                        "mein": mein,
                        "import": imp,
                    }
                )
    return konflikte


def zusammenfuehren(meine: Daten, import_: Daten, wahl: dict[str, str]) -> tuple[Daten, dict]:
    """wahl: Konflikt-id -> "mein" oder "import"; fehlende Einträge behalten den eigenen Wert."""
    neu = copy.deepcopy(meine)
    info = {"neue_jahre": 0, "neue_tage": 0, "konflikte_import": 0, "konflikte_mein": 0}
    for jahr, s_imp in import_.saisons.items():
        s = neu.saisons.get(jahr)
        if s is None:
            neu.saisons[jahr] = copy.deepcopy(s_imp)
            info["neue_jahre"] += 1
            info["neue_tage"] += len(s_imp.eintraege)
            continue
        if s.start != s_imp.start:
            if wahl.get(f"start:{jahr}") == "import":
                s.start = s_imp.start
                info["konflikte_import"] += 1
            else:
                info["konflikte_mein"] += 1
        for tag, betrag in s_imp.eintraege.items():
            mein = s.eintraege.get(tag)
            if mein is None:
                s.eintraege[tag] = betrag
                info["neue_tage"] += 1
            elif mein != betrag:
                if wahl.get(f"betrag:{tag.isoformat()}") == "import":
                    s.eintraege[tag] = betrag
                    info["konflikte_import"] += 1
                else:
                    info["konflikte_mein"] += 1
    return neu, info
