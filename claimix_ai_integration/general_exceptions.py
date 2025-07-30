def evaluate_general_exceptions_claim(claim):
    decision_flags = {"approved": False, "rejected": False, "pending": False}
    reasons = []

    def flag(decision_type, reason):
        decision_flags[decision_type] = True
        reasons.append(f"{decision_type.upper()}: {reason}")

    # --- War or Terrorism ---
    if claim.get("did_war_or_terrorism_occur"):
        flag("rejected", "Claim involves war, terrorism, or civil unrest — excluded under general exceptions unless required by the Road Traffic Act.")

    else:
        flag("approved", "No war or terrorism involved.")

    # --- Nuclear or Radioactive Risk ---
    if claim.get("did_nuclear_or_radioactive_risk"):
        flag("rejected", "Nuclear/radioactive material risk present — fully excluded under general exceptions.")
    else:
        flag("approved", "No nuclear or radioactive risk reported.")

    # --- Pollution or Contamination ---
    if claim.get("did_pollution_or_contamination"):
        flag("pending", "Pollution/contamination involved — only covered if sudden, identifiable, and accidental. Further investigation needed.")
    else:
        flag("approved", "No pollution or contamination involved.")

    # --- Alcohol or Drugs ---
    if claim.get("was_alcohol_or_drugs_involved"):
        flag("rejected", "Driver under influence of alcohol or drugs — only legal liability may apply under compulsory law. Otherwise excluded.")
    else:
        flag("approved", "No alcohol or drug use involved.")

    # --- Cyber Attack ---
    if claim.get("did_cyber_attack_occur"):
        flag("rejected", "Cyber attack present — fully excluded unless RTA requires legal liability to be paid.")
    else:
        flag("approved", "No cyber attack involved.")

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
