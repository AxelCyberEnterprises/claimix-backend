import datetime

def evaluate_special_liability_situations_claim(claim):
    decision_flags = {"approved": False, "rejected": False, "pending": False}
    reasons = []

    def flag(decision_type, reason):
        decision_flags[decision_type] = True
        reasons.append(f"{decision_type.upper()}: {reason}")

    # --- Incident Date & Time ---
    try:
        datetime.datetime.strptime(claim["incident_date"], "%Y-%m-%d")
        flag("approved", "Incident date is valid.")
    except:
        flag("pending", "Invalid or missing incident date.")

    if "incident_time" in claim:
        if isinstance(claim["incident_time"], str) and ":" in claim["incident_time"]:
            flag("approved", "Incident time format appears valid.")
        else:
            flag("pending", "Incident time format is invalid.")

    # --- Driving Other Cars Extension ---
    if claim.get("did_use_driving_other_cars_extension"):
        if not claim.get("was_permission_given_by_owner"):
            flag("rejected", "Permission from owner not granted — driving other cars cover void.")
        elif not claim.get("was_other_vehicle_insured"):
            flag("rejected", "The other vehicle was not insured — driving other cars cover excluded.")
        else:
            flag("approved", "Driving other cars extension applied — meets conditions for third-party liability.")

    # --- Towing Situations ---
    if claim.get("did_towing_occur"):
        item_type = claim.get("towed_item_type", "unspecified")
        if claim.get("was_towing_for_hire_or_reward"):
            flag("rejected", "Towing for hire/reward — excluded from cover.")
        elif item_type in ["trailer", "caravan", "broken_vehicle", "other"]:
            flag("rejected", f"Towing a {item_type} — excluded under liability terms.")
        else:
            flag("pending", "Towing activity reported but item type unspecified.")

    # --- Charging Cable Liability ---
    if claim.get("was_charging_cable_in_use"):
        if claim.get("did_cable_cause_damage_or_injury"):
            if claim.get("was_due_care_taken_with_cable"):
                flag("approved", "Damage/injury from charging cable covered — due care confirmed.")
            else:
                flag("rejected", "Due care was not taken with charging cable — excluded under policy.")
        else:
            flag("approved", "Charging cable was in use but no damage/injury — no liability triggered.")

    # --- Location Restrictions ---
    if claim.get("did_incident_occur_in_non_public_location"):
        flag("approved", "Incident occurred off public road — may still be valid under private liability conditions.")

    # --- Autonomous Vehicle Liability (AEVA 2018) ---
    if claim.get("was_vehicle_in_autonomous_mode"):
        if not claim.get("was_incident_in_gb_only"):
            flag("rejected", "Autonomous mode incident occurred outside Great Britain — excluded by AEVA region restrictions.")
        elif not claim.get("was_safety_software_updated"):
            flag("rejected", "Critical OTA safety update not installed — autonomous coverage void.")
        elif claim.get("was_vehicle_software_modified"):
            flag("rejected", "Vehicle software was modified — invalidates autonomous driving coverage.")
        else:
            flag("approved", "Autonomous vehicle incident covered under AEVA 2018 — all conditions met.")

    # --- Final Decision ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No actionable coverage paths matched or inputs missing.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
