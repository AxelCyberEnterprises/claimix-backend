def evaluate_admin_and_underwriting_claim(claim):
    decision_flags = {"approved": False, "rejected": False, "pending": False}
    reasons = []

    def flag(decision_type, reason):
        decision_flags[decision_type] = True
        reasons.append(f"{decision_type.upper()}: {reason}")

    # --- Policy Status ---
    if claim.get("is_policy_active") is False:
        flag("rejected", "Policy is inactive — no cover applies.")
    elif claim.get("is_policy_active") is True:
        flag("approved", "Policy is currently active.")
    else:
        flag("pending", "Policy status not confirmed.")

    # --- Premium Status ---
    if claim.get("is_premium_paid_up_to_date") is False:
        flag("rejected", "Premium payments are not up to date — cover is invalid.")
    elif claim.get("is_premium_paid_up_to_date") is True:
        flag("approved", "Premiums are up to date.")
    else:
        flag("pending", "Unable to verify premium payment status.")

    # --- NCD (No Claim Discount) ---
    if "no_claim_discount_years" in claim:
        ncd_years = claim["no_claim_discount_years"]
        flag("approved", f"NCD applied with {ncd_years} year(s).")
        if claim.get("is_ncd_protected"):
            flag("approved", "NCD is protected — future claims won't affect discount (terms apply).")
        else:
            flag("pending", "NCD not protected — future claims may reduce discount.")
    else:
        flag("pending", "No claim discount info missing.")

    # --- Proof of Identity & Address ---
    if claim.get("was_proof_of_identity_provided"):
        flag("approved", "Proof of identity provided.")
    else:
        flag("pending", "Proof of identity missing — required for verification.")

    if claim.get("was_proof_of_address_provided"):
        flag("approved", "Proof of address provided.")
    else:
        flag("pending", "Proof of address missing — required for verification.")

    # --- Final Decision Logic ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    else:
        final_decision = "approved"

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
