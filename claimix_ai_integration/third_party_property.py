import datetime

def evaluate_third_party_property_damage_claim(claim):
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

    # --- Property Damage Evaluation ---
    if claim.get("did_property_damage_occur"):
        flag("approved", "Third-party property damage occurred — covered under liability to others.")
        
        value = claim.get("estimated_property_damage_value", None)
        if value is not None:
            if value <= 20_000_000:
                flag("approved", f"Estimated damage (£{value}) is within policy limit of £20,000,000.")
            else:
                flag("pending", f"Damage value (£{value}) may exceed policy limit — legal review required.")
        else:
            flag("pending", "Estimated property damage value not provided.")

        description = claim.get("third_party_property_description", "").strip()
        if description:
            flag("approved", f"Property description provided: {description}.")
        else:
            flag("pending", "Property damage occurred but description is missing.")

        if claim.get("was_liability_limit_exceeded") is True:
            flag("pending", "Reported that liability limit was exceeded — subject to legal review.")
    else:
        flag("rejected", "No third-party property damage reported — claim not valid under this section.")

    # --- Final Decision Logic ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No coverage path matched or claim missing required details.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
