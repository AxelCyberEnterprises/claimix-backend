import datetime

def evaluate_bodily_injury_fatality_claim(claim):
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
        if isinstance(claim["incident_time"], str) and ":" in claim["incident_time"]:
            flag("approved", "Incident time format is valid.")
        else:
            flag("pending", "Incident time format is invalid.")

    # --- Third-Party Injuries ---
    if claim.get("were_third_parties_injured"):
        count = claim.get("number_of_injured_parties", 0)
        if count > 0:
            flag("approved", f"{count} third-party injury/ies reported — covered under liability to others.")
        else:
            flag("pending", "Injury reported but number of injured parties not specified.")
    else:
        flag("approved", "No third-party injuries reported.")

    # --- Fatalities ---
    if claim.get("were_there_fatalities"):
        flag("approved", "Fatalities occurred — covered under bodily injury liability and subject to legal cost protections.")
    else:
        flag("approved", "No fatalities reported.")

    # --- Emergency Medical Treatment ---
    if claim.get("was_emergency_medical_treatment_paid"):
        if claim.get("did_pay_emergency_treatment_under_rta"):
            flag("approved", "Emergency medical treatment was paid under RTA — covered and does not affect NCD.")
        else:
            flag("pending", "Medical treatment paid but not confirmed as RTA-related — clarification required.")
    else:
        flag("approved", "No emergency medical treatment reported.")

    # --- Legal Proceedings ---
    if claim.get("is_coroners_inquest_required"):
        flag("approved", "Coroner's inquest is covered under legal costs section.")

    if claim.get("is_manslaughter_defence_needed"):
        flag("approved", "Defence in manslaughter case is covered — legal protection applies.")

    # --- Police or Witness Reference ---
    if "police_or_witness_reference" in claim:
        if claim["police_or_witness_reference"].strip():
            flag("approved", "Police or witness reference provided.")
        else:
            flag("pending", "Police or witness reference is empty — recommended for serious incidents.")
    else:
        flag("pending", "No police or witness reference provided.")

    # --- Final Decision ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No actionable claim elements provided or missing key details.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
