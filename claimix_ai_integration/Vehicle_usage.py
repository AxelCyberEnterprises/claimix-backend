def evaluate_territorial_and_usage_claim(claim):
    decision_flags = {"approved": False, "rejected": False, "pending": False}
    reasons = []

    def flag(decision_type, reason):
        decision_flags[decision_type] = True
        reasons.append(f"{decision_type.upper()}: {reason}")

    # --- Territorial Limits ---
    if claim.get("was_incident_within_great_britain_ni_ci_iom") is True:
        flag("approved", "Incident occurred within covered regions (Great Britain, NI, Isle of Man, Channel Islands).")
    else:
        days_abroad = claim.get("days_spent_abroad_in_eu", None)
        if days_abroad is not None:
            if days_abroad <= 180:
                flag("approved", f"Incident occurred in EU within 180-day limit — European cover applies (excludes Republic of Ireland from this limit).")
            else:
                flag("rejected", f"Vehicle abroad for {days_abroad} days — exceeds 180-day limit for EU cover.")
        else:
            flag("pending", "Territorial limits not met and days abroad not specified — requires clarification.")

    # --- Use for Hire or Reward (e.g., transporting people/goods for payment) ---
    if claim.get("did_use_for_hire_or_reward") is True:
        flag("rejected", "Vehicle was used for hire or reward — usage not covered by standard private policy.")
    else:
        flag("approved", "Vehicle was not used for hire or reward.")

    # --- Use for Courier or Taxi ---
    if claim.get("did_use_for_courier_or_taxi") is True:
        flag("rejected", "Courier or taxi usage — excluded under policy use conditions.")

    # --- Track/Race Use ---
    if claim.get("did_use_on_track_days_or_racing") is True:
        flag("rejected", "Vehicle used on track days or racing — strictly excluded from cover.")
    else:
        flag("approved", "Vehicle not used for track or racing — usage compliant.")

    # --- Off-Road Use ---
    if claim.get("did_use_off_road") is True:
        flag("pending", "Vehicle used off-road — eligibility depends on location and purpose (may be partially covered).")
    elif claim.get("did_use_off_road") is False:
        flag("approved", "Vehicle was not used off-road.")

    # --- Final Decision ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: Insufficient input to determine territorial or usage eligibility.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
