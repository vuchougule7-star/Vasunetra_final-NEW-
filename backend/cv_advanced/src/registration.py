import cv2
import numpy as np


def find_features(image):

    orb = cv2.ORB_create(
        nfeatures=3000
    )

    keypoints, descriptors = orb.detectAndCompute(
        image,
        None
    )

    if descriptors is None:
        raise ValueError(
            "Could not detect enough features."
        )

    return keypoints, descriptors


def match_features(
    descriptors1,
    descriptors2
):

    matcher = cv2.BFMatcher(
        cv2.NORM_HAMMING
    )

    knn_matches = matcher.knnMatch(
        descriptors1,
        descriptors2,
        k=2
    )

    good_matches = []

    for pair in knn_matches:

        if len(pair) != 2:
            continue

        best, second = pair

        if best.distance < 0.75 * second.distance:
            good_matches.append(best)

    good_matches = sorted(
        good_matches,
        key=lambda match: match.distance
    )

    return good_matches


def align_images(
    before,
    after,
    keypoints1,
    keypoints2,
    matches
):

    if len(matches) < 4:

        raise ValueError(
            "Not enough good matches for alignment."
        )

    points1 = np.float32([
        keypoints1[m.queryIdx].pt
        for m in matches
    ]).reshape(-1, 1, 2)

    points2 = np.float32([
        keypoints2[m.trainIdx].pt
        for m in matches
    ]).reshape(-1, 1, 2)

    # =========================================
    # 1. HOMOGRAPHY + RANSAC
    # =========================================

    homography, inlier_mask = cv2.findHomography(
        points2,
        points1,
        cv2.RANSAC,
        5.0
    )

    if homography is None:
        raise ValueError(
            "Could not calculate homography."
        )

    height, width = before.shape[:2]

    aligned_after = cv2.warpPerspective(
        after,
        homography,
        (width, height)
    )

    # =========================================
    # 2. ECC REFINEMENT
    # =========================================

    before_gray = cv2.cvtColor(
        before,
        cv2.COLOR_BGR2GRAY
    )

    aligned_gray = cv2.cvtColor(
        aligned_after,
        cv2.COLOR_BGR2GRAY
    )

    warp_matrix = np.eye(
        2,
        3,
        dtype=np.float32
    )

    criteria = (
        cv2.TERM_CRITERIA_EPS
        | cv2.TERM_CRITERIA_COUNT,
        30,
        1e-5
    )

    ecc_correlation = 0.0

    try:

        cc, warp_matrix = cv2.findTransformECC(
            before_gray,
            aligned_gray,
            warp_matrix,
            cv2.MOTION_AFFINE,
            criteria
        )

        ecc_correlation = float(cc)

        aligned_after = cv2.warpAffine(
            aligned_after,
            warp_matrix,
            (width, height),
            flags=cv2.INTER_LINEAR
            | cv2.WARP_INVERSE_MAP
        )

        print(
            "ECC refinement successful."
        )

        print(
            "ECC correlation:",
            round(ecc_correlation, 4)
        )

    except cv2.error:

        print(
            "ECC refinement failed; "
            "using homography alignment."
        )

    # =========================================
    # 3. VALID OVERLAP
    # =========================================

    original_mask = np.ones(
        after.shape[:2],
        dtype=np.uint8
    ) * 255

    valid_overlap_mask = cv2.warpPerspective(
        original_mask,
        homography,
        (width, height)
    )

    # =========================================
    # 4. ALIGNMENT QUALITY
    # =========================================

    inliers = int(
        inlier_mask.sum()
    )

    total_matches = len(matches)

    ransac_confidence = (
        inliers / total_matches * 100
        if total_matches > 0
        else 0
    )

    # ECC correlation is a second measure of
    # image similarity after registration.

    if ecc_correlation > 0:

        alignment_quality = (
            0.4 * ransac_confidence
            + 0.6 * (ecc_correlation * 100)
        )

    else:

        alignment_quality = ransac_confidence

    alignment_quality = round(
        min(100, max(0, alignment_quality)),
        2
    )

    print(
        "Good matches:",
        total_matches
    )

    print(
        "RANSAC inliers:",
        inliers
    )

    print(
        "RANSAC confidence:",
        round(
            ransac_confidence,
            2
        ),
        "%"
    )

    print(
        "Alignment quality:",
        alignment_quality,
        "%"
    )

    # Keep the existing variable meaning in
    # main.py: alignment_confidence now represents
    # the combined alignment quality.

    return (
        aligned_after,
        valid_overlap_mask,
        inliers,
        total_matches,
        alignment_quality
    )