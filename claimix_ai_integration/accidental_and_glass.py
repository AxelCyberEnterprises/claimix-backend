import datetime

def evaluate_accidental_damage_glass_claim(claim):
    decision_flags = {"approved": False, "rejected": False, "pending": False}
    reasons = []

    def flag(decision_type, reason):
        decision_flags[decision_type] = True
        reasons.append(f"{decision_type.upper()}: {reason}")

    # --- Date and Time ---
    try:
        datetime.datetime.strptime(claim["incident_date"], "%Y-%m-%d")
        flag("approved", "Incident date is in valid format.")
    except:
        flag("pending", "Incident date format is invalid or missing.")

    if "incident_time" in claim:
        if not isinstance(claim["incident_time"], str) or not claim["incident_time"].count(":") == 1:
            flag("pending", "Incident time format is incorrect.")
        else:
            flag("approved", "Incident time format appears correct.")

    # --- Collision and Impact ---
    if claim.get("did_collision_occur"):
        flag("approved", "Collision occurred — covered under accidental damage.")
        if claim.get("was_other_vehicle_involved"):
            flag("approved", "Other vehicle involved — additional third-party cover may apply.")
            if not claim.get("other_vehicle_registration"):
                flag("pending", "Other vehicle involved but registration missing.")
            if not claim.get("other_vehicle_make_and_model"):
                flag("pending", "Other vehicle involved but make/model missing.")
        else:
            flag("approved", "No other vehicle involved — single-vehicle collision covered.")
    else:
        flag("pending", "No collision occurred — not eligible under accidental damage unless other covered event applies.")

    if claim.get("did_strike_object"):
        if claim.get("object_struck_description"):
            flag("approved", "Struck object described — eligible under accidental damage.")
        else:
            flag("pending", "Object was struck but not described.")

    if "estimated_speed_at_impact_mph" in claim:
        speed = claim["estimated_speed_at_impact_mph"]
        if speed >= 0:
            flag("approved", f"Speed at impact noted: {speed} mph.")
        else:
            flag("pending", "Estimated speed at impact is invalid.")

    # --- Location ---
    if "location_type" in claim:
        flag("approved", f"Incident location: {claim['location_type'].replace('_',' ')}.")

    # --- Vandalism ---
    if claim.get("did_vandalism_occur"):
        if claim.get("was_vandalism_reported"):
            flag("approved", "Vandalism occurred and was reported — covered under accidental damage.")
            if not claim.get("vandalism_crime_reference"):
                flag("pending", "Vandalism report missing crime reference.")
        else:
            flag("pending", "Vandalism occurred but was not reported to the police — please file a police report.")

    # --- Wrong Fuel ---
    if claim.get("did_wrong_fuel_occur"):
        if claim.get("were_fuel_drain_receipts_provided"):
            flag("approved", "Wrong fuel added — receipts provided — covered.")
        else:
            flag("pending", "Wrong fuel added — pending receipt submission or repair agreement.")

    # --- Glass Damage ---
    if claim.get("did_glass_damage_occur"):
        glass_type = claim.get("glass_component_type", "unspecified")
        flag("approved", f"Glass damage reported to {glass_type.replace('_', ' ')} — covered.")

        if claim.get("was_adas_recalibration_needed"):
            flag("approved", "ADAS recalibration required and covered.")
        else:
            flag("approved", "ADAS recalibration not required or not indicated.")

        if not claim.get("did_use_recommended_repairer"):
            flag("pending", "Non-recommended repairer used — additional excess may apply.")

        if claim.get("is_glass_only_claim"):
            flag("approved", "Glass-only claim — processed under glass section.")

    # --- Final decision logic ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No valid inputs matched covered events or supporting details missing.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
