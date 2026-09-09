from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .scoring import load_and_score
from .cv_pipeline import run_core_pipeline, run_advanced_pipeline

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT.parent / "frontend"
MEDIA_ROOT = ROOT / "uploads"
MEDIA_ROOT.mkdir(exist_ok=True)
STATE_FILE = ROOT / "analysis_state.json"

app = FastAPI(title="Vasunetra Disaster Management API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
app.mount("/official", StaticFiles(directory=FRONTEND / "official", html=True), name="official")
app.mount("/field", StaticFiles(directory=FRONTEND / "field", html=True), name="field")
app.mount("/citizen", StaticFiles(directory=FRONTEND / "citizen", html=True), name="citizen")
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")


def _clean_rows(df: pd.DataFrame):
    return df.replace({float("nan"): None}).to_dict(orient="records")



def _save_analysis_state(village: str, land_change_score: float, payload: dict, job_id: str):
    state = {"land_change": {}, "latest": {}}
    if STATE_FILE.exists():
        try:
            loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    state.setdefault("land_change", {})
    state["land_change"][village] = round(float(land_change_score), 6)
    state["latest"] = {"village": village, "job_id": job_id, "result": payload}
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _normalise_change_result(results: dict) -> dict:
    adv = results.get("advanced")
    core = results.get("core")
    selected = adv or core
    if not selected:
        raise ValueError("No OpenCV result was produced")
    if adv:
        change = adv.get("change", {})
        return {
            "engine": "advanced",
            "change_percentage": float(change.get("detected_change_percentage", 0)),
            "confidence": float(change.get("confidence_score", 0)),
            "significant_regions": int(change.get("significant_region_count", 0)),
            "alignment_confidence": float(adv.get("alignment", {}).get("alignment_confidence", 0)),
            "hazard": adv.get("assessment", {}),
            "files": adv.get("files", {}),
        }
    change = core.get("change", {})
    return {
        "engine": "core",
        "change_percentage": float(change.get("changed_area_pct", 0)),
        "confidence": float(core.get("evidence_confidence", {}).get("score", 0)),
        "significant_regions": int(change.get("significant_regions", 0)),
        "alignment_confidence": float(core.get("alignment", {}).get("alignment_confidence", 0)),
        "hazard": {},
        "files": core.get("files", {}),
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "vasunetra", "version": "1.0.0"}


@app.get("/api/villages")
def get_villages():
    return _clean_rows(load_and_score())


@app.get("/api/worklist")
def get_worklist():
    df = load_and_score()
    top = df[["village", "hazard_score", "relocation_score", "recommended_action", "high_population_flag"]]
    return _clean_rows(top)


@app.get("/api/villages/{name}")
def get_village_detail(name: str):
    df = load_and_score()
    row = df[df["village"] == name]
    if row.empty:
        raise HTTPException(status_code=404, detail="village not found")
    return _clean_rows(row)[0]



@app.post("/api/detect-change")
async def detect_change_endpoint(
    before: UploadFile = File(...),
    after: UploadFile = File(...),
    village: str | None = Form(None),
):
    """Canonical Field endpoint: two images -> the core OpenCV pipeline -> JSON."""
    payload = await analyze_images(before=before, after=after, engine="core", village=village)
    normalized = payload["normalized"]
    return {
        "job_id": payload["core"]["job_id"],
        "village": village,
        "engine": "core",
        "change_percentage": normalized["change_percentage"],
        "confidence": normalized["confidence"],
        "alignment_confidence": normalized["alignment_confidence"],
        "significant_regions": normalized["significant_regions"],
        "land_change_score": payload["land_change_score"],
        "hazard": normalized["hazard"],
        "files": normalized["files"],
        "updated_village_data": payload.get("updated_village_data"),
    }

@app.get("/api/jobs/{job_id}/report")
def download_report(job_id: str):
    """Return the saved analysis report for a completed job."""
    report = MEDIA_ROOT / job_id / "advanced" / "final_assessment.json"
    if not report.exists():
        report = MEDIA_ROOT / job_id / "core" / "result.json"
    if not report.exists():
        raise HTTPException(status_code=404, detail="analysis report not found")
    return FileResponse(report, media_type="application/json", filename=f"redzone-sentinel-{job_id}.json")


@app.post("/api/analyze")
async def analyze_images(
    before: UploadFile = File(...),
    after: UploadFile = File(...),
    engine: str = "core",
    village: str | None = Form(None),
):
    engine = engine.lower().strip()
    if engine not in {"core", "advanced", "both"}:
        raise HTTPException(status_code=400, detail="engine must be core, advanced or both")

    job_id = uuid.uuid4().hex
    job_dir = MEDIA_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    before_path = job_dir / f"before{Path(before.filename or '').suffix or '.jpg'}"
    after_path = job_dir / f"after{Path(after.filename or '').suffix or '.jpg'}"

    with before_path.open("wb") as f:
        shutil.copyfileobj(before.file, f)
    with after_path.open("wb") as f:
        shutil.copyfileobj(after.file, f)

    try:
        results = {}
        if engine in {"core", "both"}:
            results["core"] = run_core_pipeline(before_path, after_path, job_id=job_id)
        if engine in {"advanced", "both"}:
            results["advanced"] = run_advanced_pipeline(before_path, after_path, job_id=job_id)

        # Expose a score-ready land_change value for the village scorer: percentage -> 0..1.
        normalized = _normalise_change_result(results)
        results["land_change_score"] = round(normalized["change_percentage"] / 100.0, 4)
        results["normalized"] = normalized
        if village:
            villages = load_and_score()["village"].astype(str).tolist()
            if village not in villages:
                raise HTTPException(status_code=400, detail=f"unknown village: {village}")
            _save_analysis_state(village, results["land_change_score"], results, job_id)
            results["updated_village"] = village
            results["updated_village_data"] = _clean_rows(load_and_score())[next(i for i, row in enumerate(_clean_rows(load_and_score())) if row["village"] == village)]
        return results
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Image analysis failed: {exc}") from exc


REPORTS_FILE = ROOT / "reports.json"
REPORTS_FILE.touch(exist_ok=True)

def _load_reports():
    try:
        value = json.loads(REPORTS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []

def _save_report(item):
    reports = _load_reports()
    reports.insert(0, item)
    REPORTS_FILE.write_text(json.dumps(reports[:100], indent=2), encoding="utf-8")

@app.get("/api/summary")
def get_summary():
    df = load_and_score()
    return {
        "villages": int(len(df)),
        "high_risk": int((df["hazard_score"] > 0.55).sum()),
        "needs_action": int(df["recommended_action"].isin(["Immediate Verification", "Relocation Assessment"]).sum()),
        "land_change_alerts": int((df["land_change"] > 0).sum()),
        "high_capacity_pressure": int((df["capacity_pressure"] >= 0.75).sum()),
        "latest_analysis": json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else None,
    }

@app.get("/api/alerts")
def get_alerts():
    df = load_and_score()
    alerts = []
    for _, row in df.head(5).iterrows():
        tier = "HIGH" if row["hazard_score"] > .55 else ("MEDIUM" if row["hazard_score"] > .35 else "LOW")
        if tier != "LOW":
            alerts.append({
                "village": row["village"],
                "severity": tier,
                "message": f'{row["recommended_action"]} recommended. Hazard score {row["hazard_score"]*100:.0f}/100.',
                "land_change": round(float(row["land_change"]*100), 2),
            })
    return alerts

@app.get("/api/safe-zones/{village}")
def get_safe_zone(village: str):
    df = load_and_score()
    row = df[df["village"].astype(str) == village]
    if row.empty:
        raise HTTPException(status_code=404, detail="village not found")
    r = row.iloc[0]
    return {
        "village": village,
        "name": r.get("safe_zone", "Designated Community Safe Zone"),
        "distance_km": float(r.get("safe_zone_distance_km", 2.5)),
        "latitude": float(r.get("safe_zone_lat", r.get("latitude", 23.73))),
        "longitude": float(r.get("safe_zone_lon", r.get("longitude", 92.68))),
        "capacity": int(r.get("shelter_capacity", 300)),
        "capacity_status": r.get("capacity_status", "Prototype estimate"),
    }

@app.post("/api/citizen/report")
async def citizen_report(payload: dict):
    issue = str(payload.get("issue", "")).strip()
    village = str(payload.get("village", "Unknown")).strip()
    if not issue:
        raise HTTPException(status_code=400, detail="Issue description is required")
    report = {
        "id": uuid.uuid4().hex[:10],
        "village": village,
        "issue": issue[:500],
        "status": "Received",
        "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    _save_report(report)
    return report

@app.get("/api/reports")
def get_reports():
    return _load_reports()[:30]

@app.get("/")
def root():
    return FileResponse(FRONTEND / "landing.html")
