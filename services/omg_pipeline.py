from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


BASE_W, BASE_H = 1920, 1080
ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "omg"
VENDOR_LAYOUT = ASSET_ROOT / "layout_coordinates.json"
VENDOR_MODEL = ASSET_ROOT / "ability_classifier_fp16.onnx"
VENDOR_CLASSES = ASSET_ROOT / "class_names.json"
# These optional metadata files are needed only by the offline import-api CLI,
# not by the Discord screenshot processing path.
ODOTA_ABILITY_IDS = ASSET_ROOT / "ability_ids.json"
ODOTA_ABILITIES = ASSET_ROOT / "abilities.json"
ODOTA_HEROES = ASSET_ROOT / "heroes.json"
TIER_COLORS = {
    "T0": (245, 177, 35),
    "T1": (232, 72, 42),
    "T2": (28, 181, 214),
    "T3": (83, 112, 135),
    "T4": (55, 58, 65),
}
RECOMMENDATION_BORDER_RED = (255, 48, 48)
RECOMMENDATION_BORDER_YELLOW = (255, 205, 32)
PICK_TIER_COLORS = {
    "P0": (255, 43, 214),
    "P1": (0, 229, 255),
    "P2": (39, 140, 122),
    "P3": (105, 119, 134),
    "P4": (75, 80, 88),
}
COMBO_PAIR_COLOR = (255, 214, 48)
COMBO_TRIPLET_COLOR = (255, 64, 224)


@dataclass(frozen=True)
class Slot:
    slot_id: str
    kind: str
    bbox: tuple[int, int, int, int]


def build_layout() -> list[Slot]:
    if VENDOR_LAYOUT.exists():
        data = json.loads(VENDOR_LAYOUT.read_text(encoding="utf-8"))["resolutions"]["1920x1080"]
        slots: list[Slot] = []
        for item in data["models_coords"]:
            x, y, w, h = item["x"], item["y"], item["width"], item["height"]
            slots.append(Slot(f"model_h{item['hero_order']}", "model", (x, y, x + w, y + h)))
        for item in data["ultimate_slots_coords"]:
            x, y, w, h = item["x"], item["y"], item["width"], item["height"]
            slots.append(Slot(f"ultimate_h{item['hero_order']}", "ability", (x, y, x + w, y + h)))
        for item in data["standard_slots_coords"]:
            x, y, w, h = item["x"], item["y"], item["width"], item["height"]
            slots.append(Slot(f"standard_h{item['hero_order']}_a{item['ability_order']}", "ability", (x, y, x + w, y + h)))
        return slots

    slots: list[Slot] = []

    # Upper 12 special/ultimate slots: two rows of six.
    for row, y in enumerate((151, 248)):
        for col, x in enumerate((680, 773, 865, 958, 1050, 1143)):
            slots.append(Slot(f"ultimate_r{row + 1}c{col + 1}", "ability", (x, y, x + 76, y + 76)))

    # Six hero rows in the upper standard panel.
    upper_ys = (342, 410, 477)
    for row, y in enumerate(upper_ys):
        slots.append(Slot(f"model_upper_left_{row + 1}", "model", (606, y, 671, y + 68)))
        slots.append(Slot(f"model_upper_right_{row + 1}", "model", (1237, y, 1302, y + 68)))
        for col, x in enumerate((694, 786, 878)):
            slots.append(Slot(f"standard_ul_r{row + 1}c{col + 1}", "ability", (x, y, x + 78, y + 68)))
        for col, x in enumerate((981, 1073, 1165)):
            slots.append(Slot(f"standard_ur_r{row + 1}c{col + 1}", "ability", (x, y, x + 78, y + 68)))

    # Six hero rows in the lower standard panel.
    lower_ys = (590, 660, 756)
    for row, y in enumerate(lower_ys):
        slots.append(Slot(f"model_lower_left_{row + 1}", "model", (579, y, 648, y + 75)))
        slots.append(Slot(f"model_lower_right_{row + 1}", "model", (1268, y, 1337, y + 75)))
        for col, x in enumerate((672, 765, 857)):
            slots.append(Slot(f"standard_ll_r{row + 1}c{col + 1}", "ability", (x, y, x + 79, y + 75)))
        for col, x in enumerate((979, 1072, 1164)):
            slots.append(Slot(f"standard_lr_r{row + 1}c{col + 1}", "ability", (x, y, x + 79, y + 75)))
    return slots


def scaled_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    sx, sy = width / BASE_W, height / BASE_H
    x1, y1, x2, y2 = bbox
    return tuple(round(v) for v in (x1 * sx, y1 * sy, x2 * sx, y2 * sy))  # type: ignore[return-value]


def icon_hash(image: Image.Image, size: int = 16) -> int:
    """Difference hash, robust to scaling and minor screenshot compression."""
    gray = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    px = list(gray.getdata())
    value = 0
    bit = 0
    for y in range(size):
        row = y * (size + 1)
        for x in range(size):
            if px[row + x] > px[row + x + 1]:
                value |= 1 << bit
            bit += 1
    return value


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def inner_crop(image: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
    crop = image.crop(bbox)
    w, h = crop.size
    # Remove frames, selection glow, and badge area from matching input.
    margin_x, margin_y = max(4, round(w * 0.14)), max(4, round(h * 0.14))
    return crop.crop((margin_x, margin_y, w - margin_x, h - margin_y))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def locate(image_path: Path, out_json: Path, crops_dir: Path | None) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    rows = []
    if crops_dir:
        crops_dir.mkdir(parents=True, exist_ok=True)
    for slot in build_layout():
        bbox = scaled_bbox(slot.bbox, *image.size)
        row = {"slot_id": slot.slot_id, "kind": slot.kind, "bbox": list(bbox)}
        rows.append(row)
        if crops_dir:
            inner_crop(image, bbox).save(crops_dir / f"{slot.slot_id}.png")
    result = {"schema_version": 1, "image": str(image_path), "image_size": list(image.size), "slots": rows}
    write_json(out_json, result)
    return result


def load_templates(index_path: Path) -> list[dict[str, Any]]:
    data = read_json(index_path)
    templates = []
    for item in data.get("items", []):
        path = (index_path.parent / item["image"]).resolve()
        image = Image.open(path).convert("RGB")
        templates.append({**item, "hash": icon_hash(image)})
    return templates


def recognize(image_path: Path, template_index: Path, threshold: float = 0.82) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    templates = load_templates(template_index)
    rows = []
    bits = 16 * 16
    for slot in build_layout():
        bbox = scaled_bbox(slot.bbox, *image.size)
        target_hash = icon_hash(inner_crop(image, bbox))
        candidates = [t for t in templates if t.get("kind") == slot.kind]
        ranked = sorted(((hamming(target_hash, t["hash"]), t) for t in candidates), key=lambda x: x[0])
        distance, best = ranked[0] if ranked else (bits, None)
        confidence = 1.0 - distance / bits
        accepted = best is not None and confidence >= threshold
        rows.append({
            "slot_id": slot.slot_id,
            "kind": slot.kind,
            "bbox": list(bbox),
            "status": "matched" if accepted else "unknown",
            "confidence": round(confidence, 4),
            "entity_id": best.get("id") if accepted else None,
            "name": best.get("name") if accepted else None,
        })
    return {"schema_version": 1, "image": str(image_path), "image_size": list(image.size), "slots": rows}


def recognize_onnx(
    image_path: Path,
    model_path: Path = VENDOR_MODEL,
    classes_path: Path = VENDOR_CLASSES,
    threshold: float = 0.90,
) -> dict[str, Any]:
    """Batch-recognize the 48 ability slots with the vendored MobileNetV2 model."""
    try:
        import numpy as np
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("recognize-onnx requires numpy and onnxruntime") from exc

    image = Image.open(image_path).convert("RGB")
    class_names = json.loads(classes_path.read_text(encoding="utf-8"))
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    all_slots = build_layout()
    ability_slots = [slot for slot in all_slots if slot.kind == "ability"]
    batch = []
    bboxes = []
    for slot in ability_slots:
        bbox = scaled_bbox(slot.bbox, *image.size)
        crop = image.crop(bbox).resize((96, 96), Image.Resampling.BILINEAR)
        batch.append(np.asarray(crop, dtype=np.float32))
        bboxes.append(bbox)
    scores = session.run([output_name], {input_name: np.stack(batch, axis=0)})[0]

    rows = []
    for slot, bbox, probs in zip(ability_slots, bboxes, scores):
        index = int(np.argmax(probs))
        confidence = float(probs[index])
        accepted = confidence >= threshold
        name = class_names[index] if accepted else None
        rows.append({
            "slot_id": slot.slot_id,
            "kind": "ability",
            "bbox": list(bbox),
            "status": "matched" if accepted else "unknown",
            "confidence": round(confidence, 6),
            "entity_id": name,
            "name": name,
            "class_index": index,
            "best_candidate": class_names[index],
        })

    # Hero model recognition uses a separate NCC template library. Preserve all
    # 12 coordinates explicitly and mark them unknown until that library exists.
    for slot in (s for s in all_slots if s.kind == "model"):
        rows.append({
            "slot_id": slot.slot_id,
            "kind": "model",
            "bbox": list(scaled_bbox(slot.bbox, *image.size)),
            "status": "unknown",
            "confidence": 0.0,
            "entity_id": None,
            "name": None,
        })
    rows.sort(key=lambda x: x["slot_id"])
    return {
        "schema_version": 1,
        "engine": "ability-draft-plus-mobilenetv2-fp16",
        "threshold": threshold,
        "image": str(image_path),
        "image_size": list(image.size),
        "slots": rows,
    }


def percentile_tiers(items: list[dict[str, Any]]) -> dict[str, str]:
    valid = [x for x in items if isinstance(x.get("value"), (int, float))]
    valid.sort(key=lambda x: float(x["value"]), reverse=True)
    tiers = {}
    count = max(1, len(valid))
    for rank, item in enumerate(valid):
        p = rank / count
        tier = "T0" if p < 0.05 else "T1" if p < 0.20 else "T2" if p < 0.50 else "T3" if p < 0.80 else "T4"
        tiers[str(item["id"])] = tier
    return tiers


def pick_position_tiers(items: list[dict[str, Any]]) -> dict[str, str]:
    """Rank average draft position; an earlier pick receives a higher P tier."""
    valid = [x for x in items if isinstance(x.get("avg_pick"), (int, float))]
    valid.sort(key=lambda x: float(x["avg_pick"]))
    tiers = {}
    count = max(1, len(valid))
    for rank, item in enumerate(valid):
        p = rank / count
        tier = "P0" if p < 0.05 else "P1" if p < 0.20 else "P2" if p < 0.50 else "P3" if p < 0.80 else "P4"
        tiers[str(item["id"])] = tier
    return tiers


def recommendation_border_color(tier: str | None, pick_tier: str | None) -> tuple[int, int, int] | None:
    """Return the combined value/pick recommendation border, strongest rule first."""
    if tier not in ("T0", "T1"):
        return None
    # P0/P1 also satisfy "P2 or better"; the narrower yellow rule wins.
    if pick_tier in ("P0", "P1"):
        return RECOMMENDATION_BORDER_YELLOW
    if pick_tier == "P2":
        return RECOMMENDATION_BORDER_RED
    return None


def reticle_arms(
    bbox: tuple[int, int, int, int], length: int, image_size: tuple[int, int]
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Build four outward 45-degree corner arms, clipped to the image."""
    x1, y1, x2, y2 = bbox
    image_w, image_h = image_size
    corners = (
        ((x1, y1), (-1, -1)),
        ((x2, y1), (1, -1)),
        ((x1, y2), (-1, 1)),
        ((x2, y2), (1, 1)),
    )
    arms = []
    for start, (dx, dy) in corners:
        end = (
            min(max(start[0] + dx * length, 0), image_w - 1),
            min(max(start[1] + dy * length, 0), image_h - 1),
        )
        arms.append((start, end))
    return arms


def import_windrun_sqlite(database_path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    metadata = {row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM Metadata")}
    items: list[dict[str, Any]] = []
    for row in connection.execute(
        "SELECT ability_id, name, display_name, winrate, high_skill_winrate, pick_rate FROM Abilities"
    ):
        items.append({
            "id": row["name"],
            "windrun_id": row["ability_id"],
            "name": row["name"],
            "display_name": row["display_name"],
            "kind": "ability",
            "win_rate": row["winrate"],
            "high_skill_win_rate": row["high_skill_winrate"],
            "pick_rate": row["pick_rate"],
            # Bundled DB does not retain Windrun's valuation field. Ranking by
            # unified win rate is explicit and reproducible instead of invented.
            "value": row["winrate"],
        })
    for row in connection.execute(
        "SELECT hero_id, name, display_name, winrate, windrun_id, high_skill_winrate, pick_rate FROM Heroes"
    ):
        items.append({
            "id": row["name"],
            "windrun_id": row["windrun_id"] or row["hero_id"],
            "name": row["name"],
            "display_name": row["display_name"],
            "kind": "model",
            "win_rate": row["winrate"],
            "high_skill_win_rate": row["high_skill_winrate"],
            "pick_rate": row["pick_rate"],
            "value": row["winrate"],
        })
    tiers = percentile_tiers(items)
    for item in items:
        item["tier"] = tiers.get(str(item["id"]))
    return {
        "schema_version": 1,
        "source": str(database_path),
        "updated_at": metadata.get("lastScrapeDate") or metadata.get("last_scrape_date"),
        "tier_basis": "unified_win_rate_percentile",
        "items": items,
    }


def import_windrun_api(
    api_path: Path,
    database_path: Path,
    ability_ids_path: Path = ODOTA_ABILITY_IDS,
    abilities_meta_path: Path = ODOTA_ABILITIES,
    heroes_meta_path: Path = ODOTA_HEROES,
) -> dict[str, Any]:
    """Convert a saved `/api/v2/abilities` response into the local unified schema."""
    payload = read_json(api_path)
    data = payload["data"]
    stats = data["abilityStats"]
    valuations = data.get("abilityValuations", {})
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    db_abilities = list(connection.execute("SELECT name, display_name FROM Abilities"))
    by_internal = {row["name"]: (row["name"], row["display_name"]) for row in db_abilities}
    by_display = {
        str(row["display_name"]).casefold(): (row["name"], row["display_name"])
        for row in db_abilities
        if row["display_name"]
    }
    valve_names: dict[int, str] = {}
    for raw_ids, internal in read_json(ability_ids_path).items():
        for raw_id in str(raw_ids).split(","):
            valve_names[int(raw_id)] = internal
    valve_meta = read_json(abilities_meta_path)
    ability_names: dict[int, tuple[str, str | None]] = {}
    for valve_id, internal in valve_names.items():
        mapped = by_internal.get(internal)
        if mapped is None:
            display = valve_meta.get(internal, {}).get("dname")
            if display:
                mapped = by_display.get(str(display).casefold())
        if mapped is not None:
            ability_names[valve_id] = mapped
    db_heroes = list(connection.execute("SELECT name, display_name FROM Heroes"))
    heroes_by_internal = {row["name"]: (row["name"], row["display_name"]) for row in db_heroes}
    heroes_by_display = {
        str(row["display_name"]).casefold(): (row["name"], row["display_name"])
        for row in db_heroes if row["display_name"]
    }
    hero_names: dict[int, tuple[str, str | None]] = {}
    for raw_id, meta in read_json(heroes_meta_path).items():
        internal = str(meta.get("name", "")).removeprefix("npc_dota_hero_")
        mapped = heroes_by_internal.get(internal)
        if mapped is None and meta.get("localized_name"):
            mapped = heroes_by_display.get(str(meta["localized_name"]).casefold())
        if mapped is not None:
            hero_names[int(raw_id)] = mapped

    items: list[dict[str, Any]] = []
    unknown_ids: list[int] = []
    for stat in stats:
        api_id = int(stat["abilityId"])
        if api_id < 0:
            mapped = hero_names.get(-api_id)
            kind = "model"
        else:
            mapped = ability_names.get(api_id)
            kind = "ability"
        if mapped is None:
            unknown_ids.append(api_id)
            continue
        name, display_name = mapped
        value = valuations.get(str(api_id))
        items.append({
            "id": name,
            "windrun_id": api_id,
            "name": name,
            "display_name": display_name,
            "kind": kind,
            "owner_hero_id": stat.get("ownerHero") if kind == "ability" else None,
            "num_picks": stat.get("numPicks"),
            "win_rate": stat.get("winrate"),
            "avg_pick": stat.get("avgPickPosition"),
            "pick_rate": stat.get("pickRate"),
            "value": value,
        })
    tiers = percentile_tiers(items)
    for item in items:
        item["tier"] = tiers.get(str(item["id"]))
    return {
        "schema_version": 1,
        "source": str(api_path),
        "updated_at": data.get("_lastUpdated"),
        "patches": data.get("patches"),
        "tier_basis": "windrun_value_percentile",
        "unmapped_windrun_ids": unknown_ids,
        "items": items,
    }


def merge(recognition_path: Path, stats_path: Path) -> dict[str, Any]:
    recognition = read_json(recognition_path)
    stats = read_json(stats_path)
    items = stats.get("items", [])
    by_id = {str(item["id"]): item for item in items}
    models_by_hero_id = {
        abs(int(item["windrun_id"])): item
        for item in items
        if item.get("kind") == "model" and isinstance(item.get("windrun_id"), int)
    }
    derived = percentile_tiers(items)
    derived_pick_tiers = pick_position_tiers(items)
    source_rows = [dict(slot) for slot in recognition.get("slots", [])]

    # Infer each model from whatever ownerHero evidence is available. Slots or
    # stats may be absent, so never assume that all four abilities exist.
    owners_by_order: dict[int, list[int]] = {}
    for slot in source_rows:
        if slot.get("kind") != "ability" or slot.get("status") != "matched":
            continue
        match = re.search(r"_h(\d+)(?:_|$)", str(slot.get("slot_id")))
        stat = by_id.get(str(slot.get("entity_id")))
        owner = stat.get("owner_hero_id") if stat else None
        if match and isinstance(owner, int):
            owners_by_order.setdefault(int(match.group(1)), []).append(owner)

    for slot in source_rows:
        match = re.fullmatch(r"model_h(\d+)", str(slot.get("slot_id")))
        if not match:
            continue
        hero_order = int(match.group(1))
        votes = owners_by_order.get(hero_order, [])
        slot["inference"] = {
            "method": "ability_owner_majority",
            "available_votes": len(votes),
            "missing_votes": max(0, 4 - len(votes)),
            "vote_counts": {str(k): v for k, v in sorted(Counter(votes).items())},
        }
        if not votes:
            slot["inference"]["reason"] = "no_owner_evidence"
            continue
        owner_hero_id, vote_count = Counter(votes).most_common(1)[0]
        # Agreement from one or more observations is usable. When observations
        # conflict, require a strict majority; a tie remains unknown.
        if len(set(votes)) > 1 and vote_count <= len(votes) / 2:
            slot["inference"]["reason"] = "conflicting_owner_evidence"
            continue
        model = models_by_hero_id.get(owner_hero_id)
        if model is None:
            slot["inference"].update({
                "owner_hero_id": owner_hero_id,
                "winning_votes": vote_count,
                "reason": "missing_model_stats",
            })
            continue
        slot["status"] = "matched"
        slot["entity_id"] = model["id"]
        slot["name"] = model["name"]
        slot["confidence"] = round(vote_count / len(votes), 4)
        slot["inference"].update({
            "owner_hero_id": owner_hero_id,
            "winning_votes": vote_count,
            "reason": "strict_majority" if len(set(votes)) > 1 else "unanimous_available_evidence",
        })

    rows = []
    for slot in source_rows:
        row = dict(slot)
        entity_id = row.get("entity_id")
        stat = by_id.get(str(entity_id)) if entity_id is not None else None
        if row.get("status") == "matched" and stat:
            row["display_name"] = stat.get("display_name") or stat.get("name")
            row["stats"] = {
                "win_rate": stat.get("win_rate"),
                "avg_pick": stat.get("avg_pick"),
                "value": stat.get("value"),
            }
            row["tier"] = stat.get("tier") or derived.get(str(entity_id))
            row["pick_tier"] = derived_pick_tiers.get(str(entity_id))
            row["status"] = "ready" if row["tier"] in TIER_COLORS else "missing_tier"
        else:
            row["tier"] = None
            row["pick_tier"] = None
            if row.get("status") == "matched":
                row["status"] = "missing_stats"
        rows.append(row)
    return {
        "schema_version": 1,
        "image": recognition.get("image"),
        "image_size": recognition.get("image_size"),
        "windrun_updated_at": stats.get("updated_at"),
        "slots": rows,
    }


def draw_combo_links(
    draw: ImageDraw.ImageDraw,
    slots: list[dict[str, Any]],
    combo_recommendations: dict[str, tuple[dict, ...]],
    image_size: tuple[int, int],
) -> None:
    """Connect every on-screen member of a qualified Windrun combo."""
    centers: dict[str, tuple[int, int]] = {}
    for slot in slots:
        entity_id = slot.get("entity_id")
        bbox = slot.get("bbox")
        if slot.get("status") != "ready" or not entity_id or not bbox:
            continue
        x1, y1, x2, y2 = bbox
        centers.setdefault(str(entity_id), ((x1 + x2) // 2, (y1 + y2) // 2))

    line_width = max(3, round(image_size[0] / BASE_W * 4))
    for group, color in (
        ("triplets", COMBO_TRIPLET_COLOR),
        ("pairs", COMBO_PAIR_COLOR),
    ):
        for combo in combo_recommendations.get(group, ()):
            points = [centers.get(str(entity_id)) for entity_id in combo.get("entity_ids", ())]
            if len(points) < 2 or any(point is None for point in points):
                continue
            resolved = [point for point in points if point is not None]
            segments = list(zip(resolved, resolved[1:]))
            if len(resolved) == 3:
                segments.append((resolved[-1], resolved[0]))
            for start, end in segments:
                draw.line((start, end), fill=(8, 8, 8), width=line_width + 5)
            for start, end in segments:
                draw.line((start, end), fill=color, width=line_width)
            radius = line_width + 2
            for x, y in resolved:
                draw.ellipse(
                    (x - radius, y - radius, x + radius, y + radius),
                    fill=color,
                    outline=(8, 8, 8),
                    width=max(2, line_width // 2),
                )


def annotate(
    image_path: Path,
    result_path: Path,
    out_path: Path,
    combo_recommendations: dict[str, tuple[dict, ...]] | None = None,
) -> None:
    image = Image.open(image_path).convert("RGB")
    result = read_json(result_path)
    draw = ImageDraw.Draw(image)
    if combo_recommendations:
        draw_combo_links(draw, result.get("slots", []), combo_recommendations, image.size)
    badge_font_size = max(10, round(image.width / BASE_W * 12))
    try:
        badge_font = ImageFont.truetype("arialbd.ttf", badge_font_size)
    except OSError:
        badge_font = ImageFont.load_default()
    border_width = max(3, round(image.width / BASE_W * 4))
    for slot in result.get("slots", []):
        tier = slot.get("tier")
        if slot.get("status") != "ready" or tier not in TIER_COLORS:
            continue
        x1, y1, x2, y2 = slot["bbox"]
        border_color = recommendation_border_color(tier, slot.get("pick_tier"))
        if border_color:
            # Draw inward so the complete highlight remains inside the slot and
            # does not obscure adjacent draft icons.
            inset = border_width // 2
            draw.rounded_rectangle(
                (x1 + inset, y1 + inset, x2 - inset, y2 - inset),
                radius=max(3, border_width), outline=border_color,
                width=border_width,
            )
            arm_length = max(7, round(image.width / BASE_W * 10))
            arms = reticle_arms((x1, y1, x2, y2), arm_length, image.size)
            # A dark under-stroke keeps the reticle visible on similarly colored
            # icons and bright UI elements.
            for start, end in arms:
                draw.line((start, end), fill=(10, 10, 10), width=border_width + 3)
            for start, end in arms:
                draw.line((start, end), fill=border_color, width=border_width)
        text_bbox = draw.textbbox((0, 0), tier, font=badge_font, stroke_width=1)
        width = text_bbox[2] - text_bbox[0] + 6
        height = text_bbox[3] - text_bbox[1] + 4
        draw.rounded_rectangle((x1, y1, x1 + width, y1 + height), radius=4, fill=TIER_COLORS[tier], outline=(15, 15, 15), width=2)
        draw.text((x1 + 3, y1 + 1), tier, font=badge_font, fill="white", stroke_width=1, stroke_fill="black")
        pick_tier = slot.get("pick_tier")
        if pick_tier in PICK_TIER_COLORS:
            pick_bbox = draw.textbbox((0, 0), pick_tier, font=badge_font, stroke_width=1)
            pick_width = pick_bbox[2] - pick_bbox[0] + 6
            pick_height = pick_bbox[3] - pick_bbox[1] + 4
            draw.rounded_rectangle(
                (x2 - pick_width, y1, x2, y1 + pick_height),
                radius=4,
                fill=PICK_TIER_COLORS[pick_tier],
                outline=(15, 15, 15),
                width=2,
            )
            draw.text(
                (x2 - pick_width + 3, y1 + 1),
                pick_tier,
                font=badge_font,
                fill="white",
                stroke_width=1,
                stroke_fill="black",
            )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic OMG screenshot -> JSON -> Windrun tier overlay pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("locate")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--out-json", type=Path, required=True)
    p.add_argument("--crops", type=Path)

    p = sub.add_parser("recognize")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--templates", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--threshold", type=float, default=0.82)

    p = sub.add_parser("recognize-onnx")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", type=Path, default=VENDOR_MODEL)
    p.add_argument("--classes", type=Path, default=VENDOR_CLASSES)
    p.add_argument("--threshold", type=float, default=0.90)

    p = sub.add_parser("merge")
    p.add_argument("--recognition", type=Path, required=True)
    p.add_argument("--stats", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)

    p = sub.add_parser("import-sqlite")
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)

    p = sub.add_parser("import-api")
    p.add_argument("--api-json", type=Path, required=True)
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--ability-ids", type=Path, default=ODOTA_ABILITY_IDS)
    p.add_argument("--abilities-meta", type=Path, default=ODOTA_ABILITIES)
    p.add_argument("--heroes-meta", type=Path, default=ODOTA_HEROES)
    p.add_argument("--out", type=Path, required=True)

    p = sub.add_parser("annotate")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--result", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)

    p = sub.add_parser("run")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--templates", type=Path, required=True)
    p.add_argument("--stats", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--threshold", type=float, default=0.82)

    args = parser.parse_args()
    if args.command == "locate":
        locate(args.image, args.out_json, args.crops)
    elif args.command == "recognize":
        write_json(args.out, recognize(args.image, args.templates, args.threshold))
    elif args.command == "recognize-onnx":
        write_json(args.out, recognize_onnx(args.image, args.model, args.classes, args.threshold))
    elif args.command == "merge":
        write_json(args.out, merge(args.recognition, args.stats))
    elif args.command == "import-sqlite":
        write_json(args.out, import_windrun_sqlite(args.database))
    elif args.command == "import-api":
        write_json(
            args.out,
            import_windrun_api(
                args.api_json, args.database, args.ability_ids,
                args.abilities_meta, args.heroes_meta,
            ),
        )
    elif args.command == "annotate":
        annotate(args.image, args.result, args.out)
    elif args.command == "run":
        args.out_dir.mkdir(parents=True, exist_ok=True)
        recognition_path = args.out_dir / "recognition.json"
        result_path = args.out_dir / "result.json"
        write_json(recognition_path, recognize(args.image, args.templates, args.threshold))
        write_json(result_path, merge(recognition_path, args.stats))
        annotate(args.image, result_path, args.out_dir / "annotated.png")


if __name__ == "__main__":
    main()
