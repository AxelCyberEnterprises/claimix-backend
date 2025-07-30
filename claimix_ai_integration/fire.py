import datetime

def evaluate_fire_incident_claim(claim):
    decision_flags = {"approved": False, "rejected": False, "pending": False}
    reasons = []

    def flag(decision_type, reason):
        decision_flags[decision_type] = True
        reasons.append(f"{decision_type.upper()}: {reason}")

    # --- Incident Date and Time ---
    try:
        datetime.datetime.strptime(claim["incident_date"], "%Y-%m-%d")
        flag("approved", "Incident date is valid.")
    except:
        flag("pending", "Invalid or missing incident date.")

    if "incident_time" in claim:
        if not isinstance(claim["incident_time"], str) or not claim["incident_time"].count(":") == 1:
            flag("pending", "Incident time format is incorrect.")
        else:
            flag("approved", "Incident time format appears correct.")

    # --- Fire, Lightning, Explosion ---
    if claim.get("did_fire_occur") or claim.get("did_lightning_occur") or claim.get("did_explosion_occur"):
        flag("approved", "Incident caused by fire/lightning/explosion — all are covered events under fire/theft section.")
    else:
        flag("rejected", "None of the covered events (fire/lightning/explosion) occurred — not eligible under fire/theft section.")

    # --- Fire Origin and Extent ---
    if "fire_origin_area" in claim:
        flag("approved", f"Fire origin noted: {claim['fire_origin_area'].replace('_', ' ')}.")
    else:
        flag("pending", "Fire origin area not specified.")

    if "fire_damage_extent" in claim:
        flag("approved", f"Fire damage extent: {claim['fire_damage_extent']}.")
    else:
        flag("pending", "Extent of fire damage not provided.")

    # --- Reporting Requirements ---
    if claim.get("was_fire_reported"):
        if claim.get("fire_crime_reference"):
            flag("approved", "Fire was reported and crime reference is available.")
        else:
            flag("pending", "Fire was reported but crime reference is missing — may delay claim.")
    else:
        flag("pending", "Fire not reported — strongly advised to file an official report to proceed.")

    # --- MOT and ADAS Software Checks ---
    if "was_mot_valid_at_time" in claim:
        if claim["was_mot_valid_at_time"]:
            flag("approved", "MOT was valid at time of fire.")
        else:
            flag("pending", "MOT was not valid at time — claim may still proceed, but this must be reviewed.")

    if "was_adas_software_up_to_date" in claim:
        if claim["was_adas_software_up_to_date"]:
            flag("approved", "ADAS software was up to date at time of fire.")
        else:
            flag("pending", "ADAS software not up to date — this may affect claim eligibility if safety-related.")

    # --- Recommended Repairer and Cost ---
    if "did_use_recommended_repairer" in claim:
        if not claim["did_use_recommended_repairer"]:
            flag("pending", "Non-recommended repairer used — additional excess may apply.")

    if "estimated_repair_cost" in claim:
        cost = claim["estimated_repair_cost"]
        if cost >= 0:
            flag("approved", f"Estimated repair cost: £{cost}")
        else:
            flag("pending", "Invalid repair cost value provided.")

    # --- Final Decision Logic ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No qualifying events or incomplete information.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
