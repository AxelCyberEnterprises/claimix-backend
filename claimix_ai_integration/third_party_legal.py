import datetime

def evaluate_legal_costs_and_statutory_payments_claim(claim):
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
            flag("approved", "Incident time format is valid.")
        else:
            flag("pending", "Incident time format is invalid or missing.")

    # --- Legal Costs ---
    if claim.get("are_legal_costs_expected"):
        if "estimated_legal_costs" in claim:
            cost = claim["estimated_legal_costs"]
            if cost >= 0:
                flag("approved", f"Legal costs expected (£{cost}) — covered for inquest or defence under policy.")
            else:
                flag("pending", "Estimated legal cost provided is invalid.")
        else:
            flag("pending", "Legal costs expected but estimate not provided.")
    else:
        flag("approved", "No legal costs expected — skipping legal coverage section.")

    # --- Statutory Payments ---
    if claim.get("are_statutory_payments_required"):
        desc = claim.get("statutory_payment_description", "").strip()
        if desc:
            flag("approved", f"Statutory payment required: {desc} — covered where legally required.")
        else:
            flag("pending", "Statutory payment indicated but no description provided.")
    else:
        flag("approved", "No statutory payments required — nothing to process under this section.")

    # --- Legal Reference Number ---
    if "legal_reference_number" in claim:
        if claim["legal_reference_number"].strip():
            flag("approved", "Legal reference number provided — supports claim validation.")
        else:
            flag("pending", "Legal reference number field is empty — may delay validation.")
    else:
        flag("pending", "Legal reference number not provided — recommended for tracking legal expenses.")

    # --- Final Decision ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: Missing key details required to evaluate legal/statutory eligibility.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
