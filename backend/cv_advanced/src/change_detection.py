import cv2
import numpy as np
import json
import os


def detect_change(before, after, valid_overlap_mask):

    # =========================================
    # 1. LAB CONVERSION
    # =========================================

    before_lab = cv2.cvtColor(
        before,
        cv2.COLOR_BGR2LAB
    )

    after_lab = cv2.cvtColor(
        after,
        cv2.COLOR_BGR2LAB
    )

    # =========================================
    # 2. INTENSITY SIGNAL
    # =========================================

    before_l = before_lab[:, :, 0]
    after_l = after_lab[:, :, 0]

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    before_l = clahe.apply(before_l)
    after_l = clahe.apply(after_l)

    before_l = cv2.GaussianBlur(
        before_l,
        (9, 9),
        0
    )

    after_l = cv2.GaussianBlur(
        after_l,
        (9, 9),
        0
    )

    intensity_difference = cv2.absdiff(
        before_l,
        after_l
    )

    _, intensity_mask = cv2.threshold(
        intensity_difference,
        40,
        255,
        cv2.THRESH_BINARY
    )

    # =========================================
    # 3. COLOR SIGNAL
    # =========================================

    color_a = cv2.absdiff(
        before_lab[:, :, 1],
        after_lab[:, :, 1]
    )

    color_b = cv2.absdiff(
        before_lab[:, :, 2],
        after_lab[:, :, 2]
    )

    color_difference = cv2.add(
        color_a,
        color_b
    )

    color_difference = cv2.GaussianBlur(
        color_difference,
        (9, 9),
        0
    )

    _, color_mask = cv2.threshold(
        color_difference,
        45,
        255,
        cv2.THRESH_BINARY
    )

    # =========================================
    # 4. MULTI-SIGNAL VOTING
    # =========================================

    evidence_count = (
        (intensity_mask > 0).astype(np.uint8)
        + (color_mask > 0).astype(np.uint8)
    )

    # Require BOTH intensity AND color evidence
    combined_mask = np.where(
        evidence_count >= 2,
        255,
        0
    ).astype(np.uint8)

    # =========================================
    # 5. VALID OVERLAP
    # =========================================

    combined_mask = cv2.bitwise_and(
        combined_mask,
        valid_overlap_mask
    )

    # =========================================
    # 6. MORPHOLOGICAL CLEANING
    # =========================================

    kernel = np.ones(
        (7, 7),
        np.uint8
    )

    combined_mask = cv2.morphologyEx(
        combined_mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    combined_mask = cv2.morphologyEx(
        combined_mask,
        cv2.MORPH_OPEN,
        kernel
    )

    # =========================================
    # 7. CONNECTED COMPONENTS
    # =========================================

    num_labels, labels, stats, centroids = (
        cv2.connectedComponentsWithStats(
            combined_mask,
            connectivity=8
        )
    )

    cleaned_mask = np.zeros_like(
        combined_mask
    )

    valid_area = cv2.countNonZero(
        valid_overlap_mask
    )

    # Ignore tiny regions
    minimum_area = max(
        5000,
        int(valid_area * 0.0002)
    )

    regions = []

    for i in range(1, num_labels):

        area = stats[
            i,
            cv2.CC_STAT_AREA
        ]

        x = stats[
            i,
            cv2.CC_STAT_LEFT
        ]

        y = stats[
            i,
            cv2.CC_STAT_TOP
        ]

        width = stats[
            i,
            cv2.CC_STAT_WIDTH
        ]

        height = stats[
            i,
            cv2.CC_STAT_HEIGHT
        ]

        # Ignore tiny regions
        if area < minimum_area:
            continue

        # =====================================
        # LARGE / SPARSE REGION FILTER
        # =====================================

        bounding_area = width * height

        density = (
            area / bounding_area
            if bounding_area > 0
            else 0
        )

        # Large sparse regions are usually caused
        # by perspective or lighting differences.

        if (
            bounding_area > valid_area * 0.20
            and density < 0.35
        ):
            continue

        # =====================================
        # REGION METRICS
        # =====================================

        cx, cy = centroids[i]

        area_percentage = (
            area / valid_area * 100
            if valid_area > 0
            else 0
        )

        cleaned_mask[
            labels == i
        ] = 255

        regions.append({

            "id": len(regions) + 1,

            "area_pixels": int(area),

            "area_percentage": round(
                area_percentage,
                4
            ),

            "bounding_box": {
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height)
            },

            "centroid": {
                "x": round(float(cx), 2),
                "y": round(float(cy), 2)
            },

            "density": round(
                float(density),
                4
            )
        })

    # =========================================
    # 8. CHANGE METRICS
    # =========================================

    changed_pixels = cv2.countNonZero(
        cleaned_mask
    )

    change_percentage = (
        changed_pixels / valid_area * 100
        if valid_area > 0
        else 0
    )

    region_count = len(regions)

    largest_region = max(
        regions,
        key=lambda r: r["area_pixels"],
        default=None
    )

    # =========================================
    # 9. CONFIDENCE SCORE
    # =========================================

    if region_count == 0:

        coherence_score = 0

    else:

        large_regions = [
            r for r in regions
            if r["area_percentage"] >= 0.1
        ]

        coherence_score = min(
            100,
            len(large_regions) * 20
        )

    coverage_score = min(
        100,
        change_percentage * 5
    )

    confidence = (
        0.5 * coherence_score
        + 0.5 * coverage_score
    )

    confidence = round(
        min(100, max(0, confidence)),
        2
    )

    # =========================================
    # 10. CREATE EVIDENCE OVERLAY
    # =========================================

    overlay = before.copy()

    contours, _ = cv2.findContours(
        cleaned_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    cv2.drawContours(
        overlay,
        contours,
        -1,
        (0, 0, 255),
        3
    )

    for region in regions:

        x = region["bounding_box"]["x"]
        y = region["bounding_box"]["y"]
        w = region["bounding_box"]["width"]
        h = region["bounding_box"]["height"]

        cv2.rectangle(
            overlay,
            (x, y),
            (x + w, y + h),
            (0, 255, 255),
            2
        )

        cv2.putText(
            overlay,
            f"R{region['id']}",
            (x, max(20, y - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )

    # =========================================
    # 11. SAVE OUTPUTS
    # =========================================

    os.makedirs(
        "outputs",
        exist_ok=True
    )

    cv2.imwrite(
        "outputs/change_regions.jpg",
        cleaned_mask
    )

    cv2.imwrite(
        "outputs/change_overlay.jpg",
        overlay
    )

    # =========================================
    # 12. SAVE METRICS
    # =========================================

    metrics = {

        "detected_change_percentage": round(
            change_percentage,
            4
        ),

        "significant_region_count":
            region_count,

        "largest_region":
            largest_region,

        "confidence_score":
            confidence,

        "minimum_region_area":
            minimum_area,

        "regions":
            regions
    }

    with open(
        "outputs/change_metrics.json",
        "w"
    ) as file:

        json.dump(
            metrics,
            file,
            indent=4
        )

    # =========================================
    # 13. TERMINAL OUTPUT
    # =========================================

    print()
    print("========== CHANGE ANALYSIS ==========")

    print(
        "Detected change:",
        round(change_percentage, 2),
        "%"
    )

    print(
        "Significant regions:",
        region_count
    )

    if largest_region:

        print(
            "Largest region:",
            largest_region["area_pixels"],
            "pixels"
        )

    else:

        print(
            "Largest region: 0 pixels"
        )

    print(
        "Confidence score:",
        confidence,
        "%"
    )

    print(
        "Change regions saved to:",
        "outputs/change_regions.jpg"
    )

    print(
        "Overlay saved to:",
        "outputs/change_overlay.jpg"
    )

    print(
        "Metrics saved to:",
        "outputs/change_metrics.json"
    )

    print(
        "====================================="
    )

    return cleaned_mask