from pathlib import Path
import json
import pandas as pd

DATA_FILE = Path(__file__).parent / "data" / "villages.csv"
STATE_FILE = Path(__file__).parent / "analysis_state.json"


def load_land_change_overrides():
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data.get("land_change", {}) if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_and_score(csv_path=DATA_FILE):
    df = pd.read_csv(csv_path)

    # Defaults keep the scorer backwards-compatible with a minimal dataset.
    defaults = {
        "land_change": 0.0, "vulnerability_index": 0.5,
        "shelter_capacity": 300, "safe_zone_access": 0.5,
        "capacity_pressure": 0.5, "safe_zone_distance_km": 2.5,
        "latitude": 23.73, "longitude": 92.68,
    }
    for col, value in defaults.items():
        if col not in df.columns:
            df[col] = value
        else:
            df[col] = df[col].fillna(value)

    overrides = load_land_change_overrides()
    if overrides:
        df["land_change"] = df.apply(
            lambda row: float(overrides.get(str(row["village"]), row["land_change"])),
            axis=1,
        )

    # Transparent prototype model: the hazard score uses physical/environmental
    # indicators; relocation priority adds human exposure and capacity pressure.
    df["hazard_score"] = (
        0.40 * df["slope"] +
        0.35 * df["rainfall"] +
        0.25 * df["land_change"]
    ).clip(0, 1)

    df["population_norm"] = df["population"] / max(float(df["population"].max()), 1.0)
    df["access_factor"] = 1 - df["access_score"]
    df["capacity_pressure"] = (
        df["population"] / df["shelter_capacity"].clip(lower=1)
    ).clip(0, 1)

    df["relocation_score"] = (
        0.70 * df["hazard_score"] +
        0.12 * df["population_norm"] +
        0.08 * df["access_factor"] +
        0.05 * df["vulnerability_index"] +
        0.05 * df["capacity_pressure"]
    ).clip(0, 1)

    pop_threshold = df["population"].quantile(0.75)
    df["high_population_flag"] = df["population"] > pop_threshold
    df["capacity_status"] = df["capacity_pressure"].apply(
        lambda x: "Over capacity" if x >= 1 else
        ("High pressure" if x >= 0.75 else
         ("Moderate pressure" if x >= 0.50 else "Available"))
    )

    def action_for(row):
        score = row["hazard_score"]
        relocation = row["relocation_score"]
        if score >= 0.75 or relocation >= 0.72:
            return "Immediate Verification"
        if score >= 0.55 or relocation >= 0.55:
            return "Relocation Assessment"
        if score >= 0.35:
            return "Enhanced Monitoring"
        return "Routine Monitoring"

    df["recommended_action"] = df.apply(action_for, axis=1)
    df["priority_rank"] = df["relocation_score"].rank(method="min", ascending=False).fillna(len(df)).astype(int)
    df["hazard_contribution"] = 0.85 * df["hazard_score"]
    df["population_contribution"] = 0.10 * df["population_norm"]
    df["access_contribution"] = 0.05 * df["access_factor"]

    return df.sort_values(["relocation_score", "hazard_score"], ascending=False).reset_index(drop=True)
