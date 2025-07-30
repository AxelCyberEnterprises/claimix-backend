import datetime

def evaluate_personal_belongings_claim(claim):
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

    # --- Items Lost or Damaged ---
    if not claim.get("did_items_become_lost_or_damaged"):
        flag("rejected", "No items were lost or damaged — claim is not valid under this section.")
    else:
        flag("approved", "Personal belongings reported as lost or damaged.")

    # --- Item List and Total Value ---
    if "item_list" in claim and isinstance(claim["item_list"], list):
        if not claim["item_list"]:
            flag("pending", "Item list is empty — please provide descriptions and values.")
        else:
            for item in claim["item_list"]:
                desc = item.get("description", "").lower()
                value = item.get("estimated_value", 0)
                if any(banned in desc for banned in [
                    "money", "stamps", "tickets", "documents", "securities",
                    "trade", "tools", "equipment", "already insured"
                ]):
                    flag("rejected", f"Item '{desc}' appears to fall under an excluded category.")
                elif value > 300:
                    flag("pending", f"Item '{desc}' exceeds £300 limit — may need further clarification or partial approval.")
                else:
                    flag("approved", f"Item '{desc}' within acceptable policy limits.")
    else:
        flag("pending", "Item list is missing or invalid.")

    if "total_estimated_value" in claim:
        if claim["total_estimated_value"] > 300:
            flag("pending", "Total estimated value exceeds £300 — may exceed policy limit.")
        else:
            flag("approved", f"Total estimated value: £{claim['total_estimated_value']}")
    else:
        flag("pending", "Total estimated value is missing.")

    # --- Storage Condition ---
    if "were_items_stored_out_of_sight" in claim:
        if claim["were_items_stored_out_of_sight"]:
            flag("approved", "Items were stored out of sight — complies with storage condition.")
        else:
            flag("rejected", "Items not stored out of sight — violates storage requirement.")
    else:
        flag("pending", "Storage condition not confirmed — please indicate if items were out of sight.")

    # --- Final Decision Logic ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No actionable inputs provided or validation failed.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
