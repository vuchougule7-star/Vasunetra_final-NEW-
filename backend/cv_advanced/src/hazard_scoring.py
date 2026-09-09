
def calculate_hazard_score(
    change_percentage,
    change_confidence,
    alignment_confidence,
    significant_regions,
    vulnerability_score=50,
    carrying_capacity_score=50,
    relocation_need_score=50,
    field_verification_score=50
):

    # =========================================
    # 1. LAND-CHANGE SCORE
    # =========================================

    if change_percentage < 5:
        change_score = 10
    elif change_percentage < 10:
        change_score = 25
    elif change_percentage < 20:
        change_score = 45
    elif change_percentage < 30:
        change_score = 65
    else:
        change_score = 85

    # =========================================
    # 2. CHANGE REGION SCORE
    # =========================================

    if significant_regions == 0:
        region_score = 0
    elif significant_regions <= 5:
        region_score = 15
    elif significant_regions <= 15:
        region_score = 30
    elif significant_regions <= 30:
        region_score = 50
    else:
        region_score = 65

    # =========================================
    # 3. CV EVIDENCE SCORE
    # =========================================

    evidence_score = (
        change_confidence * 0.6
        + alignment_confidence * 0.4
    )

    # =========================================
    # 4. FINAL HAZARD SCORE
    # =========================================

    hazard_score = (
        change_score * 0.25
        + region_score * 0.10
        + evidence_score * 0.15
        + vulnerability_score * 0.20
        + carrying_capacity_score * 0.10
        + relocation_need_score * 0.15
        + field_verification_score * 0.05
    )

    hazard_score = round(
        min(100, max(0, hazard_score)),
        2
    )

    # =========================================
    # 5. PRIORITY
    # =========================================

    if hazard_score >= 75:
        priority = "CRITICAL"

        action = (
            "Immediate field verification, "
            "relocation assessment and "
            "priority resource allocation"
        )

    elif hazard_score >= 50:
        priority = "HIGH"

        action = (
            "Prioritize field inspection, "
            "assess carrying capacity and "
            "prepare mitigation/relocation review"
        )

    elif hazard_score >= 25:
        priority = "MODERATE"

        action = (
            "Schedule field verification, "
            "continue monitoring and reassess risk"
        )

    else:
        priority = "LOW"

        action = (
            "Continue monitoring; "
            "no immediate relocation action"
        )

    return {
        "hazard_score": hazard_score,

        "priority": priority,

        "recommended_action": action,

        "components": {
            "change_score": change_score,
            "region_score": region_score,
            "evidence_score": round(
                evidence_score,
                2
            ),
            "vulnerability_score": vulnerability_score,
            "carrying_capacity_score": carrying_capacity_score,
            "relocation_need_score": relocation_need_score,
            "field_verification_score": field_verification_score
        }
    }