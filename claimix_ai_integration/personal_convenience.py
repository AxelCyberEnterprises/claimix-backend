import datetime

def evaluate_mobility_and_continuation_services_claim(claim):
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

    # --- Guaranteed Hire Car ---
    if claim.get("did_request_guaranteed_hire_car"):
        if claim.get("was_incident_within_territorial_limits"):
            if claim.get("was_vehicle_status_repairable") or claim.get("was_vehicle_status_total_loss"):
                flag("approved", "Hire car requested and eligible — within territorial limits and vehicle status supports request.")
            else:
                flag("pending", "Hire car requested, but vehicle status not clearly marked as repairable or total loss.")
        else:
            flag("rejected", "Hire car requested but incident occurred outside territorial limits — not covered.")

    # --- Continuation of Journey ---
    if claim.get("did_request_continuation_of_journey"):
        if not claim.get("were_continuation_receipts_provided"):
            flag("pending", "Continuation of journey requested, but receipts not provided.")
        else:
            amount = claim.get("continuation_expenses_amount", 0)
            if amount <= 500:
                flag("approved", f"Continuation of journey covered — receipts provided and within £500 limit (claimed: £{amount}).")
            else:
                flag("pending", f"Continuation of journey amount (£{amount}) exceeds £500 limit — partial approval may apply or review needed.")
    else:
        flag("approved", "No continuation of journey requested — skipping that section.")

    # --- Final Decision Logic ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No actionable information provided.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
