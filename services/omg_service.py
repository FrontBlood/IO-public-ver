from __future__ import annotations

import tempfile
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from services.omg_pipeline import annotate, merge, recognize_onnx, write_json


ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "omg"
WORK_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "omg"
MODEL_PATH = ASSET_ROOT / "ability_classifier_fp16.onnx"
CLASSES_PATH = ASSET_ROOT / "class_names.json"
STATS_PATH = ASSET_ROOT / "windrun_stats.json"
ZH_NAMES_PATH = ASSET_ROOT / "zh_names.json"
PAIRS_PATH = ASSET_ROOT / "windrun_ability_pairs_7.41d.json"
TRIPLETS_PATH = ASSET_ROOT / "windrun_ability_triplets_7.41d.json"
MAX_IMAGE_PIXELS = 20_000_000
MIN_COMBO_WIN_RATE = 0.65
MIN_COMBO_SYNERGY = 0.095
MIN_PAIR_PICKS = 500
MIN_TRIPLET_PICKS = 200
MAX_COMBO_RECOMMENDATIONS = 3


class OmgInputError(ValueError):
    pass


@dataclass(frozen=True)
class OmgResult:
    image: bytes
    matched: int
    unknown: int
    recommendations: dict[str, tuple[str, ...]]
    combo_recommendations: dict[str, tuple[dict, ...]]


def build_recommendations(
    slots: list[dict], zh_names: dict[str, str]
) -> dict[str, tuple[str, ...]]:
    groups = {"first": [], "second": [], "third": []}
    seen = {"first": set(), "second": set(), "third": set()}
    for slot in slots:
        if slot.get("status") != "ready":
            continue
        tier = slot.get("tier")
        pick_tier = slot.get("pick_tier")
        if tier in ("T0", "T1") and pick_tier == "P0":
            group = "first"
        elif tier in ("T0", "T1") and pick_tier == "P1":
            group = "second"
        elif tier in ("T0", "T1", "T2") and pick_tier in ("P0", "P1", "P2"):
            group = "third"
        else:
            group = None
        if group is None:
            continue
        entity_id = str(slot.get("entity_id") or "")
        name = zh_names.get(entity_id) or slot.get("display_name") or slot.get("name") or entity_id
        if name and name not in seen[group]:
            seen[group].add(name)
            groups[group].append(name)
    return {key: tuple(value) for key, value in groups.items()}


def validate_assets() -> None:
    required = (MODEL_PATH, CLASSES_PATH, STATS_PATH, ZH_NAMES_PATH, PAIRS_PATH, TRIPLETS_PATH)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"OMG 运行文件缺失：{', '.join(missing)}")


def _wilson_lower_bound(wins: int, picks: int, z: float = 1.96) -> float:
    if picks <= 0:
        return 0.0
    rate = wins / picks
    denominator = 1 + z * z / picks
    center = rate + z * z / (2 * picks)
    margin = z * ((rate * (1 - rate) / picks + z * z / (4 * picks * picks)) ** 0.5)
    return (center - margin) / denominator


def build_combo_recommendations(
    slots: list[dict],
    stats_items: list[dict],
    pairs_payload: dict,
    triplets_payload: dict,
    zh_names: dict[str, str],
) -> dict[str, tuple[dict, ...]]:
    by_entity = {str(item["id"]): item for item in stats_items}
    by_windrun_id = {int(item["windrun_id"]): item for item in stats_items}
    available_ids = {
        int(by_entity[str(slot["entity_id"])]["windrun_id"])
        for slot in slots
        if slot.get("status") == "ready" and str(slot.get("entity_id")) in by_entity
    }

    def select(rows: list[dict], id_fields: tuple[str, ...], min_picks: int) -> tuple[dict, ...]:
        candidates = []
        for row in rows:
            combo_ids = tuple(int(row[field]) for field in id_fields)
            picks = int(row.get("numPicks") or 0)
            wins = int(row.get("wins") or 0)
            win_rate = float(row.get("winrate") or 0.0)
            if picks < min_picks or win_rate < MIN_COMBO_WIN_RATE or not set(combo_ids).issubset(available_ids):
                continue
            items = [by_windrun_id.get(combo_id) for combo_id in combo_ids]
            if any(item is None for item in items):
                continue
            origin_heroes = [
                abs(int(item["windrun_id"]))
                if item.get("kind") == "model"
                else item.get("owner_hero_id")
                for item in items
            ]
            known_origins = [origin for origin in origin_heroes if isinstance(origin, int)]
            if len(known_origins) != len(set(known_origins)):
                continue
            individual_rates = [item.get("win_rate") for item in items]
            if not all(isinstance(rate, (int, float)) for rate in individual_rates):
                continue
            synergy = win_rate - sum(float(rate) for rate in individual_rates) / len(individual_rates)
            if synergy < MIN_COMBO_SYNERGY:
                continue
            names = tuple(
                zh_names.get(str(item["id"])) or item.get("display_name") or item["name"]
                for item in items
            )
            candidates.append({
                "entity_ids": tuple(str(item["id"]) for item in items),
                "names": names,
                "win_rate": win_rate,
                "synergy": synergy,
                "picks": picks,
                "score": _wilson_lower_bound(wins, picks),
            })
        candidates.sort(
            key=lambda item: (item["synergy"], item["score"], item["win_rate"], item["picks"]),
            reverse=True,
        )
        for item in candidates:
            item.pop("score", None)
        return tuple(candidates[:MAX_COMBO_RECOMMENDATIONS])

    pair_rows = pairs_payload.get("data", {}).get("abilityPairs", [])
    triplet_rows = triplets_payload.get("data", {}).get("abilityTriplets", [])
    return {
        "pairs": select(pair_rows, ("abilityIdOne", "abilityIdTwo"), MIN_PAIR_PICKS),
        "triplets": select(
            triplet_rows,
            ("abilityIdOne", "abilityIdTwo", "abilityIdThree"),
            MIN_TRIPLET_PICKS,
        ),
    }


def process_omg_screenshot(raw_image: bytes) -> OmgResult:
    validate_assets()
    try:
        with Image.open(BytesIO(raw_image)) as probe:
            probe.verify()
        with Image.open(BytesIO(raw_image)) as probe:
            width, height = probe.size
    except (UnidentifiedImageError, OSError) as exc:
        raise OmgInputError("附件不是可识别的图片。") from exc

    if width * height > MAX_IMAGE_PIXELS:
        raise OmgInputError("图片分辨率过高，请上传不超过 2000 万像素的截图。")
    if width / height < 1.6 or width / height > 1.9:
        raise OmgInputError("截图宽高比不符合要求，请上传完整的 16:9 OMG 选技界面截图。")

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="request_", dir=WORK_ROOT) as temp_name:
        work = Path(temp_name)
        source = work / "source.png"
        recognition_path = work / "recognition.json"
        result_path = work / "result.json"
        annotated_path = work / "omg-annotated.png"

        with Image.open(BytesIO(raw_image)) as image:
            image.convert("RGB").save(source, format="PNG")
        recognition = recognize_onnx(source, MODEL_PATH, CLASSES_PATH)
        write_json(recognition_path, recognition)
        result = merge(recognition_path, STATS_PATH)
        write_json(result_path, result)
        ready = sum(slot.get("status") == "ready" for slot in result.get("slots", []))
        unknown = len(result.get("slots", [])) - ready
        zh_names = json.loads(ZH_NAMES_PATH.read_text(encoding="utf-8"))
        recommendations = build_recommendations(result.get("slots", []), zh_names)
        stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
        combo_recommendations = build_combo_recommendations(
            result.get("slots", []),
            stats.get("items", []),
            json.loads(PAIRS_PATH.read_text(encoding="utf-8")),
            json.loads(TRIPLETS_PATH.read_text(encoding="utf-8")),
            zh_names,
        )
        annotate(source, result_path, annotated_path, combo_recommendations)
        return OmgResult(
            annotated_path.read_bytes(), ready, unknown, recommendations, combo_recommendations
        )
