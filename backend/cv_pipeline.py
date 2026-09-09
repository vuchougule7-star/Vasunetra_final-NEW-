from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent
CORE_DIR = ROOT / "cv_core"
ADV_DIR = ROOT / "cv_advanced"
OUTPUT_ROOT = ROOT / "uploads"

# Keep the supplied core modules intact; this adapter makes them callable by the API.
sys.path.insert(0, str(CORE_DIR))
sys.path.insert(0, str(ROOT))
from image_loader import load_image  # noqa: E402
from quality_check import quality_report  # noqa: E402
from alignment import align_images  # noqa: E402
from change_detection import compute_change_mask, clean_mask, change_summary  # noqa: E402
from evidence import build_evidence_image  # noqa: E402
from confidence import evidence_confidence  # noqa: E402
from config import ADVANCED_MAX_IMAGE_SIDE


def _write_heatmap(base_image, mask_image, path):
    """Create a presentation-friendly heatmap overlay from a change mask."""
    if mask_image.ndim == 3:
        gray = cv2.cvtColor(mask_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = mask_image
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    gray = cv2.GaussianBlur(gray, (0, 0), 6)
    colored = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
    if base_image.shape[:2] != colored.shape[:2]:
        base_image = cv2.resize(base_image, (colored.shape[1], colored.shape[0]), interpolation=cv2.INTER_AREA)
    overlay = cv2.addWeighted(base_image, 0.58, colored, 0.42, 0)
    cv2.imwrite(str(path), overlay)
    return overlay


def run_core_pipeline(before_path: str | Path, after_path: str | Path, job_id: str | None = None) -> dict:
    job_id = job_id or uuid.uuid4().hex
    out_dir = OUTPUT_ROOT / job_id / "core"
    out_dir.mkdir(parents=True, exist_ok=True)

    before = load_image(str(before_path))
    after = load_image(str(after_path))
    q_before = quality_report(before)
    q_after = quality_report(after)

    aligned_after, valid_mask, align_diag = align_images(before, after)
    raw_mask, _signals = compute_change_mask(before, aligned_after, valid_mask=valid_mask)
    final_mask, regions = clean_mask(raw_mask)
    summary = change_summary(final_mask, regions)

    conf_score, conf_label = evidence_confidence(
        align_diag["alignment_confidence"],
        q_before["usable"],
        q_after["usable"],
        summary["significant_regions"],
    )

    evidence_path = out_dir / "evidence_report.jpg"
    build_evidence_image(
        before, aligned_after, final_mask, str(evidence_path), regions=regions
    )

    aligned_path = out_dir / "aligned_after.jpg"
    mask_path = out_dir / "change_mask.jpg"
    overlay_path = out_dir / "change_overlay.jpg"
    cv2.imwrite(str(aligned_path), aligned_after)
    cv2.imwrite(str(mask_path), final_mask)

    # A lightweight overlay for the API/dashboard, using the supplied evidence drawing logic.
    from evidence import draw_overlay
    overlay = draw_overlay(before, final_mask, regions=regions)
    cv2.imwrite(str(overlay_path), overlay)
    heatmap_path = out_dir / "heatmap.jpg"
    _write_heatmap(before, final_mask, heatmap_path)

    result = {
        "engine": "core",
        "job_id": job_id,
        "quality": {"before": q_before, "after": q_after},
        "alignment": align_diag,
        "change": summary,
        "evidence_confidence": {"score": conf_score, "label": conf_label},
        "files": {
            "evidence": f"/media/{job_id}/core/evidence_report.jpg",
            "aligned_after": f"/media/{job_id}/core/aligned_after.jpg",
            "change_mask": f"/media/{job_id}/core/change_mask.jpg",
            "change_overlay": f"/media/{job_id}/core/change_overlay.jpg",
            "heatmap": f"/media/{job_id}/core/heatmap.jpg",
        },
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2))
    return result


def run_advanced_pipeline(before_path: str | Path, after_path: str | Path, job_id: str | None = None) -> dict:
    """Run the second supplied OpenCV implementation and expose its metrics through the same API."""
    job_id = job_id or uuid.uuid4().hex
    out_dir = OUTPUT_ROOT / job_id / "advanced"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Import the supplied advanced modules without colliding with the core module names.
    if str(ADV_DIR) not in sys.path:
        sys.path.insert(0, str(ADV_DIR))
    from cv_advanced.src.registration import find_features, match_features, align_images as adv_align
    from cv_advanced.src.change_detection import detect_change
    from cv_advanced.src.hazard_scoring import calculate_hazard_score

    before = cv2.imread(str(before_path))
    after = cv2.imread(str(after_path))
    if before is None or after is None:
        raise ValueError("Could not load one or both images")

    # The supplied advanced implementation performs ECC refinement, which can
    # become slow on very large 4K images. Keep its algorithm intact but use
    # a presentation-safe working resolution.
    def resize_for_analysis(img, max_side=ADVANCED_MAX_IMAGE_SIDE):
        h, w = img.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        if scale >= 1.0:
            return img
        return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    before = resize_for_analysis(before)
    after = resize_for_analysis(after)

    before_kp, before_desc = find_features(before)
    after_kp, after_desc = find_features(after)
    matches = match_features(before_desc, after_desc)
    aligned_after, overlap_mask, inliers, total_matches, alignment_confidence = adv_align(
        before, after, before_kp, after_kp, matches
    )

    aligned_path = out_dir / "aligned_after.jpg"
    cv2.imwrite(str(aligned_path), aligned_after)

    # The supplied detector writes outputs to its own current working directory.
    # Run it in the job directory, then collect its metrics.
    import os
    previous = os.getcwd()
    os.chdir(out_dir)
    try:
        detect_change(before, aligned_after, overlap_mask)
        metrics = json.loads((out_dir / "outputs" / "change_metrics.json").read_text())
    finally:
        os.chdir(previous)

    # Reuse the supplied hazard-scoring implementation.
    hazard = calculate_hazard_score(
        metrics["detected_change_percentage"],
        metrics["confidence_score"],
        alignment_confidence,
        metrics["significant_region_count"],
    )
    heatmap_path = out_dir / "heatmap.jpg"
    difference_path = out_dir / "outputs" / "difference.jpg"
    difference_img = cv2.imread(str(difference_path), cv2.IMREAD_GRAYSCALE)
    if difference_img is None:
        # The supplied advanced detector does not always save a difference image.
        # In that case use its cleaned change mask so the dashboard always has
        # a real heatmap instead of a blank placeholder.
        difference_img = cv2.imread(str(out_dir / "outputs" / "change_regions.jpg"), cv2.IMREAD_GRAYSCALE)
    if difference_img is not None:
        _write_heatmap(before, difference_img, heatmap_path)

    result = {
        "engine": "advanced",
        "job_id": job_id,
        "alignment": {
            "inliers": inliers,
            "total_matches": total_matches,
            "alignment_confidence": alignment_confidence,
        },
        "change": metrics,
        "assessment": hazard,
        "files": {
            "aligned_after": f"/media/{job_id}/advanced/aligned_after.jpg",
            "change_regions": f"/media/{job_id}/advanced/outputs/change_regions.jpg",
            "change_overlay": f"/media/{job_id}/advanced/outputs/change_overlay.jpg",
            "difference": f"/media/{job_id}/advanced/outputs/difference.jpg",
            "heatmap": f"/media/{job_id}/advanced/heatmap.jpg",
        },
    }
    (out_dir / "final_assessment.json").write_text(json.dumps(result, indent=2))
    return result
