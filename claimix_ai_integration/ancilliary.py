import datetime

def evaluate_ancillary_property_claim(claim):
    decision_flags = {"approved": False, "rejected": False, "pending": False}
    reasons = []

    def flag(decision_type, reason):
        decision_flags[decision_type] = True
        reasons.append(f"{decision_type.upper()}: {reason}")

    # --- Incident Date ---
    try:
        datetime.datetime.strptime(claim["incident_date"], "%Y-%m-%d")
        flag("approved", "Incident date is valid.")
    except:
        flag("pending", "Invalid or missing incident date.")

    # --- In-car Equipment ---
    if claim.get("was_factory_fitted_equipment_damaged"):
        flag("approved", "Original manufacturer-fitted equipment is covered with no limit.")

    if claim.get("was_aftermarket_equipment_damaged"):
        if claim.get("was_portable_equipment_stored_out_of_sight"):
            flag("approved", "Aftermarket or portable equipment covered up to £1,000 if stored out of sight and listed under family package.")
        else:
            flag("pending", "Aftermarket or portable equipment not stored properly — coverage may be reduced or denied.")

    if "equipment_damage_value" in claim:
        value = claim["equipment_damage_value"]
        if value >= 0:
            flag("approved", f"Reported equipment damage value: £{value}")
        else:
            flag("pending", "Invalid equipment damage value.")

    # --- Child Seat ---
    if claim.get("was_child_seat_damaged"):
        flag("approved", "Child seat damage is covered.")

    # --- Roof Box ---
    if claim.get("was_roof_box_damaged"):
        flag("rejected", "Roof box is not listed as covered under additional property. Not eligible.")

    # --- Charging Cable ---
    if claim.get("was_charging_cable_damaged"):
        flag("approved", "Charging cable damage is covered if responsible party is you and due care was taken.")

    # --- New Car Replacement ---
    if claim.get("is_new_car_replacement_eligible"):
        car_age = claim.get("car_age_in_months", None)
        if car_age is not None and car_age <= 12:
            if claim.get("is_first_registered_owner") and claim.get("is_damage_over_fifty_percent"):
                flag("approved", "Eligible for new car replacement: under 1 year old, first owner, damage over 50%.")
            else:
                flag("pending", "New car replacement requested, but either not first owner or damage less than 50%.")
        else:
            flag("pending", "New car replacement not valid — car is older than 1 year.")

    # --- Guaranteed Hire Car ---
    if claim.get("did_request_guaranteed_hire_car"):
        flag("approved", "Guaranteed hire car is covered if using recommended repairer or for total loss (conditions apply).")

    # --- Continuing Journey ---
    if claim.get("did_request_continuation_of_journey"):
        if claim.get("were_continuation_receipts_provided"):
            flag("approved", f"Continuation of journey is covered up to £500. Distance: {claim.get('continuation_distance_miles', 'unknown')} miles.")
        else:
            flag("pending", "Continuation of journey requested but no receipts provided — cannot approve yet.")

    # --- Final Decision ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No matching covered items or further detail required.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
