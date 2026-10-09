from __future__ import annotations

import json
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = PROJECT_ROOT / "assets" / "omg" / "windrun_stats.json"
OUTPUT_PATH = PROJECT_ROOT / "assets" / "omg" / "zh_names.json"
ABILITY_URL = "https://www.dota2.com/datafeed/abilitylist?language=schinese"
HERO_URL = "https://www.dota2.com/datafeed/herolist?language=schinese"


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "relic-bot/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def build_localization(stats: dict, abilities_payload: dict, heroes_payload: dict) -> tuple[dict[str, str], list[str]]:
    abilities = abilities_payload["result"]["data"]["itemabilities"]
    heroes = heroes_payload["result"]["data"]["heroes"]
    abilities_by_id = {int(row["id"]): row for row in abilities}
    abilities_by_name = {str(row["name"]): row for row in abilities}
    heroes_by_id = {int(row["id"]): row for row in heroes}
    heroes_by_name = {
        str(row["name"]).removeprefix("npc_dota_hero_"): row for row in heroes
    }

    names: dict[str, str] = {}
    missing: list[str] = []
    for item in stats.get("items", []):
        entity_id = str(item["id"])
        windrun_id = item.get("windrun_id")
        if item.get("kind") == "model":
            row = heroes_by_id.get(abs(int(windrun_id))) if isinstance(windrun_id, int) else None
            row = row or heroes_by_name.get(entity_id)
        else:
            row = abilities_by_id.get(int(windrun_id)) if isinstance(windrun_id, int) else None
            row = row or abilities_by_name.get(entity_id)
            if entity_id.endswith("_ad") and (row is None or not str(row.get("name_loc", "")).strip()):
                row = abilities_by_name.get(entity_id.removesuffix("_ad"))
        localized = str(row.get("name_loc", "")).strip() if row else ""
        if localized:
            names[entity_id] = localized
        else:
            missing.append(entity_id)
    return dict(sorted(names.items())), missing


def main() -> None:
    stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    names, missing = build_localization(stats, fetch_json(ABILITY_URL), fetch_json(HERO_URL))
    OUTPUT_PATH.write_text(
        json.dumps(names, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"localized={len(names)} missing={len(missing)}")
    if missing:
        print("missing_ids=" + ",".join(missing))


if __name__ == "__main__":
    main()
