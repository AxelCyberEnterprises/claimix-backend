import datetime

def evaluate_injury_and_medical_assault_claim(claim):
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
            flag("approved", "Incident time format appears correct.")
        else:
            flag("pending", "Incident time format is invalid.")

    # --- Personal Injury ---
    if claim.get("did_personal_injury_occur"):
        injured_party = claim.get("injured_party_type")
        injury_type = claim.get("injury_type")
        within_12_months = claim.get("was_injury_within_12_months")
        seatbelt = claim.get("was_seatbelt_worn")
        drugs_or_alcohol = claim.get("was_alcohol_or_drugs_involved")

        if injured_party in ["policyholder", "partner", "named_driver"]:
            if injury_type in ["death", "limb_loss", "loss_of_sight", "loss_of_hearing", "permanent_disability"]:
                if within_12_months:
                    if seatbelt:
                        if not drugs_or_alcohol:
                            flag("approved", f"Personal accident benefit applies for {injury_type} to {injured_party}.")
                        else:
                            flag("rejected", "Claim rejected due to alcohol or drug involvement.")
                    else:
                        flag("rejected", "Seatbelt not worn — violates safety requirement for injury claims.")
                else:
                    flag("rejected", "Injury occurred outside 12-month benefit window — not eligible.")
            else:
                flag("pending", "Injury reported is not in compensable list — further review needed.")
        else:
            flag("pending", "Injured party not eligible for personal accident benefit — further validation needed.")

    else:
        flag("rejected", "No personal injury occurred — skipping injury benefit evaluation.")

    # --- Medical Expenses ---
    if claim.get("did_medical_expenses_incur"):
        amt = claim.get("medical_expenses_amount", 0)
        if amt <= 250:
            flag("approved", f"Medical expenses of £{amt} covered (≤ £250 limit).")
        else:
            flag("pending", f"Medical expenses exceed £250 limit — review for partial payout or exception.")

    # --- Road Rage Assault ---
    if claim.get("did_road_rage_assault_occur"):
        if not claim.get("was_road_rage_reported_to_police"):
            flag("pending", "Road rage assault not reported to police — reporting required.")
        elif claim.get("was_road_rage_assailant_known"):
            flag("rejected", "Assailant known — not eligible under policy terms.")
        elif claim.get("was_road_rage_provoked_by_insured"):
            flag("rejected", "Policyholder provoked road rage incident — not covered.")
        else:
            flag("approved", "Road rage assault occurred and meets all coverage conditions.")

    # --- Aggravated Theft Assault ---
    if claim.get("did_aggravated_theft_assault_occur"):
        if not claim.get("was_theft_assault_reported_to_police"):
            flag("pending", "Theft assault occurred but not reported — required for claim.")
        elif claim.get("was_theft_assailant_known"):
            flag("rejected", "Assailant known — not eligible for aggravated theft assault benefit.")
        else:
            flag("approved", "Aggravated theft assault occurred and meets policy requirements.")

    # --- Final Decision ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No qualifying benefit matched or missing information.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
