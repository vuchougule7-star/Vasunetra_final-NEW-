# Vasunetra — Intelligent Disaster Risk Decision-Support Prototype

**SIH26191 — Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations**

Vasunetra follows:

**Evidence → Risk → Priority → Action**

## What is implemented

### 1. Field evidence / OpenCV
- Before + after field image upload
- Image quality gate (sharpness + resolution)
- ORB feature detection and Hamming-distance matching
- Homography + RANSAC image registration
- Valid-overlap masking to avoid warp-border false positives
- Multi-signal change detection: intensity + Lab colour + local structure
- Morphological cleanup and connected-region analysis
- Change percentage, significant regions and evidence confidence
- Evidence report, aligned image, change mask, overlay and heatmap

### 2. Transparent risk and relocation scoring
The prototype combines slope, rainfall and measured land change into a hazard score. Relocation priority additionally considers population exposure, access difficulty, vulnerability and estimated shelter-capacity pressure.

All weights are explicit in `backend/scoring.py`. They are **prototype decision-support weights, not government thresholds**.

### 3. Official dashboard
The official dashboard retains the supplied Vasunetra visual design and adds:
- Ranked village worklist
- Risk tier and explainable score breakdown
- Vulnerability and carrying-capacity pressure
- Active alerts
- Latest field evidence
- Direct link to Field Analysis
- Live backend status

### 4. Citizen dashboard
The supplied Citizen Safety Dashboard design is retained:
- Area risk status
- Rainfall / terrain / land-change indicators
- Safety alerts
- Safe-zone map
- Safe-zone route view
- Citizen issue reporting
- Live API data with a fallback demo dataset

### 5. Backend/API
- `/api/villages`
- `/api/worklist`
- `/api/villages/{name}`
- `/api/detect-change`
- `/api/analyze`
- `/api/summary`
- `/api/alerts`
- `/api/safe-zones/{village}`
- `/api/citizen/report`
- `/api/reports`
- `/api/jobs/{job_id}/report`

## Run on Windows

1. Open this folder in VS Code.
2. Create a virtual environment:
   `py -3.11 -m venv .venv`
3. Activate it:
   `.\.venv\Scripts\Activate.ps1`
4. Install:
   `pip install -r requirements.txt`
5. Start:
   `python run.py`
6. Open:
   - Official: `http://127.0.0.1:8000/`
   - Field Analysis: `http://127.0.0.1:8000/field/`
   - Citizen: `http://127.0.0.1:8000/citizen/`
   - API health: `http://127.0.0.1:8000/api/health`

## Demo flow

1. Open Field Analysis.
2. Select a village.
3. Upload two photographs of the **same location at different times**.
4. Run Change Detection.
5. Inspect change %, confidence and visual evidence.
6. Open Official Dashboard.
7. The selected village's land-change value is incorporated into the scoring model.
8. Open Citizen Dashboard to view the community-facing risk information.

## Data note

Village coordinates, shelter capacities and some environmental values in the included CSV are **illustrative prototype data** for demonstration. They must be replaced/validated with authoritative government/GIS data before operational use.

Vasunetra detects visible image change; it does not independently prove that a change is a landslide. Field verification remains part of the decision process.

## Future scope

- Satellite/SAR ground-movement evidence
- ML models trained on validated field imagery
- Authoritative live weather/GIS feeds
- Offline/low-connectivity field workflows
- More rigorous carrying-capacity and evacuation-network modelling
