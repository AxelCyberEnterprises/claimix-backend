import datetime

def evaluate_theft_incident_claim(claim):
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
            flag("approved", "Incident time format appears valid.")
        else:
            flag("pending", "Incident time format is invalid.")

    # --- Theft Events ---
    if claim.get("did_theft_occur"):
        flag("approved", "Theft occurred — eligible under fire/theft section.")
    elif claim.get("was_theft_attempted"):
        flag("approved", "Attempted theft is also covered under fire/theft section.")
    else:
        flag("rejected", "No theft or attempted theft reported — not covered.")

    if claim.get("was_vehicle_stolen_and_recovered"):
        flag("approved", "Vehicle was recovered — further assessment may determine if repair or total loss.")

    # --- Reporting and Crime Reference ---
    if claim.get("was_theft_reported"):
        if claim.get("theft_crime_reference"):
            flag("approved", "Theft was reported and crime reference provided.")
        else:
            flag("pending", "Theft was reported but crime reference is missing.")
    else:
        flag("pending", "Theft not reported to police — please report and provide crime reference.")

    # --- Tracker Compliance ---
    if claim.get("was_tracker_installed"):
        if claim.get("was_tracker_active") is False:
            flag("rejected", "Tracker was installed but not active — this violates tracking device condition.")
        elif claim.get("was_tracker_active") is True:
            flag("approved", "Tracker installed and active — meets theft protection requirements.")
        else:
            flag("pending", "Tracker status unclear — please confirm if active at time of theft.")

    # --- Anti-Theft Behavior / Exclusions ---
    if not claim.get("was_car_locked", True):
        flag("rejected", "Car was left unlocked — theft claim excluded under general exclusions.")

    if claim.get("were_windows_or_roof_open"):
        flag("rejected", "Windows or roof were left open — excluded under general exclusions.")

    if claim.get("was_engine_left_running"):
        flag("rejected", "Engine left running unattended — theft excluded under general exclusions.")

    if claim.get("was_key_left_in_car") or claim.get("was_key_left_near_car"):
        flag("rejected", "Ignition device was left in or near the car — claim excluded under policy.")

    # --- Repairer Choice ---
    if "did_use_recommended_repairer" in claim:
        if not claim["did_use_recommended_repairer"]:
            flag("pending", "Non-recommended repairer used — excess may apply.")

    # --- Final Decision ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No qualifying theft event or essential info missing.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
