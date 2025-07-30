def evaluate_security_and_condition_compliance_claim(claim):
    decision_flags = {"approved": False, "rejected": False, "pending": False}
    reasons = []

    def flag(decision_type, reason):
        decision_flags[decision_type] = True
        reasons.append(f"{decision_type.upper()}: {reason}")

    # --- MOT Validity ---
    if claim.get("was_mot_valid") is True:
        flag("approved", "MOT was valid — meets legal requirement for cover.")
    else:
        flag("pending", "MOT was not valid — may affect eligibility depending on claim type and circumstances.")

    # --- Roadworthiness ---
    if claim.get("was_vehicle_roadworthy") is True:
        flag("approved", "Vehicle was roadworthy — satisfies general policy condition.")
    else:
        flag("rejected", "Vehicle was not roadworthy — excluded under policy duties to maintain condition.")

    # --- Tracking Device ---
    if "was_tracking_device_working" in claim:
        if claim["was_tracking_device_working"]:
            flag("approved", "Tracking device was operational — meets theft and recovery requirements.")
        else:
            flag("rejected", "Tracking device not working — violates security condition; may void theft-related claims.")
    else:
        flag("pending", "Tracking device status not provided — required for theft-related claims.")

    # --- Ignition Device Security ---
    if claim.get("was_ignition_device_secured") is True:
        flag("approved", "Ignition device was properly secured — meets security obligation.")
    else:
        flag("rejected", "Ignition device was left unsecured — excluded under policy security clauses.")

    # --- ADAS Software Compliance ---
    if "was_adas_software_up_to_date" in claim:
        if claim["was_adas_software_up_to_date"]:
            flag("approved", "ADAS/ALKS software was up to date — complies with general conditions.")
        else:
            flag("pending", "ADAS/ALKS software not up to date — may affect autonomous driving claims.")

    # --- OTA Updates ---
    if "did_accept_ota_updates" in claim:
        if claim["did_accept_ota_updates"]:
            flag("approved", "OTA updates accepted — satisfies critical update requirement.")
        else:
            flag("rejected", "Failure to install safety-critical OTA updates — excluded from cover for autonomous systems.")
    else:
        flag("pending", "OTA update acceptance status not specified — needed for autonomous driving compliance.")

    # --- Final Decision ---
    if decision_flags["rejected"]:
        final_decision = "rejected"
    elif decision_flags["pending"]:
        final_decision = "pending"
    elif decision_flags["approved"]:
        final_decision = "approved"
    else:
        final_decision = "pending"
        reasons.append("PENDING: No conclusive compliance status provided.")

    return {
        "decision": final_decision,
        "reason": " | ".join(reasons)
    }
