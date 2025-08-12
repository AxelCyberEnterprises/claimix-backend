# orchestrator.py  (concurrent-ready version)
import os
import json
import time
import threading
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from dotenv import load_dotenv

from .utils import (
    load_json, save_json, get_session_folder,
    load_claim_state, save_claim_state
)

# Import database helper
try:
    from .db_helper import get_or_create_claim, update_claim_stage, get_claim_context
except ImportError as e:
    print(f"[WARNING] Database helper import failed: {e}")
    # Mock database functions for development
    def get_or_create_claim(claim_data):
        print(f"[MOCK] Would create/update claim: {claim_data}")
        return None, False
    
    def update_claim_stage(claim_id, stage, additional_data=None):
        print(f"[MOCK] Would update claim {claim_id} to stage {stage} with data: {additional_data}")
        return True
    
    def get_claim_context(claim_id):
        print(f"[MOCK] Would retrieve context for claim {claim_id}")
        return None

# agents & helpers (unchanged imports)
from .triage_agent       import run_triage
from .clarification_call import run_clarifying_question
from .attachment_details import generate_attachment_details
from .followup_agent     import run_follow_up_agent
from .accidental_and_glass import evaluate_accidental_damage_glass_claim
from .ancilliary            import evaluate_ancillary_property_claim
from .fire                  import evaluate_fire_incident_claim
from .general_exceptions    import evaluate_general_exceptions_claim
from .general_administrative import evaluate_admin_and_underwriting_claim
from .personal_belongings   import evaluate_personal_belongings_claim
from .personal_convenience  import evaluate_mobility_and_continuation_services_claim
from .personal_injury       import evaluate_injury_and_medical_assault_claim
from .theft                 import evaluate_theft_incident_claim
from .third_party_injury    import evaluate_bodily_injury_fatality_claim
from .third_party_legal     import evaluate_legal_costs_and_statutory_payments_claim
from .third_party_liability import evaluate_special_liability_situations_claim
from .third_party_property  import evaluate_third_party_property_damage_claim
from .Vehicle_security      import evaluate_security_and_condition_compliance_claim
from .Vehicle_usage         import evaluate_territorial_and_usage_claim

load_dotenv()

# ------------------------------------------------------------------ #
SESSIONS_DIR           = "sessions"
CLAIM_FILE             = "claim.json"
CONTEXT_FILE           = "context.json"
ATTACHMENT_DATA_FILE   = "attachment_data.json"
DECISIONS_FILE         = "decisions.json"
FOLLOW_UP_FILE         = "follow_up.json"

# review-payload files
PENDING_DIR            = "pending_payloads"
PENDING_FILE_TEMPLATE  = "{}_pending.json"

# ------------------------------------------------------------------ #
INCIDENT_TYPE_TO_AGENT = {
    "accidental_and_glass_damage": "accidental_and_glass_assistant",
    "fire":                        "fire_assistant",
    "theft":                       "theft_assistant",
    "ancillary_property":          "ancillary_assistant",
    "third_party_injury":          "third_party_injury_assistant",
    "third_party_property":        "third_party_property_assistant",
    "special_liability":           "special_liability_assistant",
    "legal_and_statutory":         "legal_and_statutory_assistant",
    "personal_injury":             "personal_injury_assistant",
    "personal_convenience":        "personal_convenience_assistant",
    "personal_property":           "personal_property_assistant",
    "territorial_usage":           "territorial_and_usage_assistant",
    "general_exceptions":          "general_exceptions_assistant",
    "vehicle_security":            "vehicle_security_assistant",
    "administrative":              "administrative_assistant"
}

ASSISTANT_IDS = {
    # MODULE 1
    "accidental_and_glass_assistant": os.getenv("ACCIDENTAL_AND_GLASS_ASSISTANT_ID"),
    "fire_assistant":                 os.getenv("FIRE_ASSISTANT_ID"),
    "theft_assistant":                os.getenv("THEFT_ASSISTANT_ID"),
    "ancillary_assistant":            os.getenv("ANCILLARY_ASSISTANT_ID"),
    # MODULE 2
    "third_party_injury_assistant":   os.getenv("THIRD_PARTY_INJURY_ASSISTANT_ID"),
    "third_party_property_assistant": os.getenv("THIRD_PARTY_PROPERTY_ASSISTANT_ID"),
    "special_liability_assistant":    os.getenv("SPECIAL_LIABILITY_ASSISTANT_ID"),
    "legal_and_statutory_assistant":  os.getenv("LEGAL_AND_STATUTORY_ASSISTANT_ID"),
    # MODULE 3
    "personal_injury_assistant":      os.getenv("PERSONAL_INJURY_ASSISTANT_ID"),
    "personal_convenience_assistant": os.getenv("PERSONAL_CONVENIENCE_ASSISTANT_ID"),
    "personal_property_assistant":    os.getenv("PERSONAL_PROPERTY_ASSISTANT_ID"),
    # MODULE 4
    "territorial_and_usage_assistant":os.getenv("TERRITORIAL_AND_USAGE_ASSISTANT_ID"),
    "general_exceptions_assistant":   os.getenv("GENERAL_EXCEPTIONS_ASSISTANT_ID"),
    "vehicle_security_assistant":     os.getenv("VEHICLE_SECURITY_ASSISTANT_ID"),
    "administrative_assistant":       os.getenv("ADMINISTRATIVE_ASSISTANT_ID")
}

DECISION_ENGINE = {
    "third_party_injury_assistant":   evaluate_bodily_injury_fatality_claim,
    "accidental_and_glass_assistant": evaluate_accidental_damage_glass_claim,
    "ancillary_assistant":            evaluate_ancillary_property_claim,
    "fire_assistant":                 evaluate_fire_incident_claim,
    "theft_assistant":                evaluate_theft_incident_claim,
    "third_party_property_assistant": evaluate_third_party_property_damage_claim,
    "special_liability_assistant":    evaluate_special_liability_situations_claim,
    "legal_and_statutory_assistant":  evaluate_legal_costs_and_statutory_payments_claim,
    "personal_injury_assistant":      evaluate_injury_and_medical_assault_claim,
    "personal_convenience_assistant": evaluate_mobility_and_continuation_services_claim,
    "personal_property_assistant":    evaluate_personal_belongings_claim,
    "territorial_and_usage_assistant":evaluate_territorial_and_usage_claim,
    "general_exceptions_assistant":   evaluate_general_exceptions_claim,
    "vehicle_security_assistant":     evaluate_security_and_condition_compliance_claim,
    "administrative_assistant":       evaluate_admin_and_underwriting_claim
}

# ------------------------------------------------------------------ #
class ClaimStage:
    NEW                = "NEW"
    QUESTIONED         = "QUESTIONED"
    TRIAGED            = "TRIAGED"
    AGENTS_RUNNING     = "AGENTS_RUNNING"
    REVIEW             = "REVIEW"
    FOLLOWUP_REQUESTED = "FOLLOWUP_REQUESTED"
    AGENTS_COMPLETE    = "AGENTS_COMPLETE"
    COMPLETE           = "COMPLETE"

    VALID_TRANSITIONS = {
        NEW               : [QUESTIONED],
        QUESTIONED        : [TRIAGED, AGENTS_RUNNING],
        TRIAGED           : [AGENTS_RUNNING],
        AGENTS_RUNNING    : [REVIEW, FOLLOWUP_REQUESTED, AGENTS_COMPLETE],
        REVIEW            : [AGENTS_RUNNING],
        FOLLOWUP_REQUESTED: [AGENTS_RUNNING],
        AGENTS_COMPLETE   : [COMPLETE],
        COMPLETE          : [TRIAGED]
    }

# ------------------------------------------------------------------ #
class Orchestrator:
    def __init__(self):
        self.client = OpenAI()
        self._lock  = threading.Lock()  # protects shared file writes

    # -------- basic file helpers ----------
    def get_claim_id(self, email):
        """Get the claim ID for an email, generating one if needed."""
        claim_file = os.path.join(SESSIONS_DIR, email, CLAIM_FILE)
        if os.path.exists(claim_file):
            claim_data = load_json(claim_file)
            return claim_data.get('claim_id', email)  # Fallback to email if no claim_id
        return email

    def folder(self, email):
        """Get the session folder path, using the claim ID if available."""
        claim_id = self.get_claim_id(email)
        return get_session_folder(claim_id)
        
    def fpath(self, email, fname): 
        return os.path.join(self.folder(email), fname)
        
    def pending_dir(self, email): 
        return os.path.join(self.folder(email), PENDING_DIR)
        
    def pending_path(self, email, agent): 
        return os.path.join(self.pending_dir(email), PENDING_FILE_TEMPLATE.format(agent))

    # -------- initial state ---------------
    def init_context(self, email):
        p = self.fpath(email, CONTEXT_FILE)
        if not os.path.exists(p):
            save_json(p, {"conversation_history": [], "attachment_details": {},
                          "last_updated": time.time()})

    def init_claim(self, claim_id):
        """Initialize a new claim with the given claim ID if it doesn't exist."""
        # Create session folder using claim ID
        session_folder = get_session_folder(claim_id)
        os.makedirs(session_folder, exist_ok=True)
        os.makedirs(os.path.join(session_folder, PENDING_DIR), exist_ok=True)
        
        p = os.path.join(session_folder, CLAIM_FILE)
        
        if not os.path.exists(p):
            # Prepare initial claim data
            claim_data = {
                "claim_id": claim_id,
                "stage": ClaimStage.NEW, 
                "incident_types": {},
                "agents_run": [], 
                "agent_threads": {},
                "completed_agents": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "email": "",  # Will be updated with first message
                "subject": ""  # Will be updated with first message
            }
            
            # Save to file system
            print(f"[ORCHESTRATOR] Saving claim data to file: {p}")
            save_json(p, claim_data)
            
            # Create in database
            print(f"[ORCHESTRATOR] Creating claim in database: {claim_id}")
            try:
                db_claim_data = {
                    'claim_id': claim_id,
                    'description': 'New claim created',
                    'status': 'New',
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                get_or_create_claim(db_claim_data)
                print(f"[DB] Created new claim in database: {claim_id}")
            except Exception as e:
                print(f"[DB ERROR] Failed to create claim in database: {e}")
                # Continue with file system operations even if DB fails

    # -------- claim helpers ---------------
    def claim(self, email): return load_json(self.fpath(email, CLAIM_FILE))
    def save_claim(self, email, data): save_json(self.fpath(email, CLAIM_FILE), data)

    def transition(self, email, new_stage, additional_data=None):
        c = self.claim(email)
        print(f"[ORCHESTRATOR] Attempting to transition claim {c['claim_id']} from {c['stage']} to {new_stage}")
        if new_stage in ClaimStage.VALID_TRANSITIONS.get(c["stage"], []):
            # Update database with new stage
            try:
                update_claim_stage(
                    claim_id=c["claim_id"],
                    stage=new_stage,
                    additional_data=additional_data or {}
                )
            except Exception as e:
                print(f"[DB ERROR] Failed to update claim stage in database: {e}")
                # Continue with file system operations even if DB update fails
            c["stage"] = new_stage
            self.save_claim(email, c)

    # -------- context helpers -------------
    def update_context(self, email, user_msg, attachments=None):
        print(f"[ORCHESTRATOR] Updating context for email: {email}")
        if user_msg and user_msg.strip():
            print(f"[ORCHESTRATOR] Processing user message: {user_msg[:100]}...")
        if attachments:
            print(f"[ORCHESTRATOR] Processing {len(attachments)} attachments")
        """
        Update the conversation context with a new user message and any attachments.
        Also updates the claim in the database if this is new information.
        """
        ctx_path = self.fpath(email, CONTEXT_FILE)
        ctx = load_json(ctx_path)
        claim = self.claim(email)
        
        # Update file-based context
        if user_msg.strip():
            ctx["conversation_history"].append({
                "role": "user", 
                "content": user_msg,
                "timestamp": time.time()
            })
            
            # If this is the first user message, update the claim description
            if len(ctx["conversation_history"]) == 1 and claim["stage"] == ClaimStage.NEW:
                try:
                    update_claim_stage(
                        claim_id=claim["claim_id"],
                        stage=claim["stage"],
                        additional_data={
                            'description': user_msg[:500],  # Truncate long descriptions
                            'updated_at': datetime.now()
                        }
                    )
                except Exception as e:
                    print(f"[DB ERROR] Failed to update claim description: {e}")
        
        if attachments:
            ctx["conversation_history"].append({
                "role": "user",
                "content": f"[{len(attachments)} attachment(s)]",
                "timestamp": time.time(),
                "attachments": attachments
            })
            
        # Handle attachment details if they exist
        ad_path = self.fpath(email, ATTACHMENT_DATA_FILE)
        if os.path.exists(ad_path):
            ctx["attachment_details"] = load_json(ad_path)
            
        ctx["last_updated"] = time.time()
        save_json(ctx_path, ctx)

    # -------- message persistence ---------
    def save_agent_message(self, email, agent, content, role="assistant"):
        p = self.fpath(email, f"{agent}_messages.json")
        with self._lock:
            data = load_json(p) if os.path.exists(p) else []
            data.append({"role": role, "content": content, "timestamp": time.time()})
            save_json(p, data)
    
    # -------- agent bookkeeping -----------
    def mark_agent_complete(self, email, agent):
        with self._lock:
            claim = self.claim(email)
            done  = claim.get("completed_agents", [])
            if agent not in done:
                done.append(agent)
                claim["completed_agents"] = done
                self.save_claim(email, claim)

    def mark_agent_complete_and_check(self, email):
        with self._lock:
            claim = self.claim(email)
            completed = set(claim.get("completed_agents", []))
            all_agents = set([INCIDENT_TYPE_TO_AGENT[i] for i in claim["incident_types"]])
            # Already up to date?
        if completed == all_agents and claim["stage"] == ClaimStage.AGENTS_RUNNING:
            self.transition(email, ClaimStage.AGENTS_COMPLETE)


    # -------- follow-up -------------------
    def save_follow_up(self, email, agent, content):
        p = self.fpath(email, FOLLOW_UP_FILE)
        with self._lock:
            d = load_json(p) if os.path.exists(p) else {"responses": []}
            d["responses"].append({"agent": agent, "response": content,
                                   "timestamp": time.time()})
            save_json(p, d)

    # -------- decisions -------------------
    def overwrite_decision(self, email, agent, decision):
        p = self.fpath(email, DECISIONS_FILE)
        with self._lock:
            data = load_json(p) if os.path.exists(p) else []
            data = [d for d in data if d["agent"] != agent]
            data.append({"agent": agent, "decision": decision,
                         "timestamp": time.time()})
            save_json(p, data)

    # -------- review processor (concurrent) ------------
    def _evaluate_pending_file(self, path: str):
        info = load_json(path)
        agent   = info["agent"]
        payload = info["payload"]
        if agent not in DECISION_ENGINE:
            return path, agent, None  # unknown agent, skip
        decision = DECISION_ENGINE[agent](payload)
        return path, agent, decision

    def run_review_stage(self, email):
        pend_dir = self.pending_dir(email)
        if not os.path.isdir(pend_dir):
            return
        pending_paths = [os.path.join(pend_dir, f) for f in os.listdir(pend_dir)
                         if f.endswith("_pending.json")]

        if not pending_paths:
            return

        processed_any = False
        # Run evaluations concurrently (up to 5 workers or #files)
        with ThreadPoolExecutor(max_workers=min(5, len(pending_paths))) as ex:
            futures = {ex.submit(self._evaluate_pending_file, p): p for p in pending_paths}

            for fut in as_completed(futures):
                try:
                    path, agent, decision = fut.result()
                except Exception as e:
                    # log and skip problematic file
                    print(f"[run_review_stage] Error evaluating {futures[fut]}: {e}")
                    continue

                # mark & save
                if decision is not None:
                    self.overwrite_decision(email, agent, decision)
                    processed_any = True

                info = load_json(path)
                info["processed"] = True
                save_json(path, info)

        if processed_any:
            self.transition(email, ClaimStage.AGENTS_RUNNING)

    # -------- assistant run ---------------
    def build_context_msg(self, email):
        ctx = load_json(self.fpath(email, CONTEXT_FILE))
        out = ""
        for m in ctx["conversation_history"]:
            out += f"{m['role'].upper()}: {m['content']}\n"
        if ctx["attachment_details"]:
            out += "\nATTACHMENTS:\n"
            for k, v in ctx["attachment_details"].items():
                out += f"{k}: {v}\n"
        return out

    def run_assistant(self, email, agent):
        if agent not in ASSISTANT_IDS or not ASSISTANT_IDS[agent]:
            return
        claim = self.claim(email)
        thread_id = claim["agent_threads"].get(agent)
        if not thread_id:
            thread_id = self.client.beta.threads.create().id
            claim["agent_threads"][agent] = thread_id
            self.save_claim(email, claim)

        ctx_msg = self.build_context_msg(email)
        self.save_agent_message(email, agent, ctx_msg, role="user")
        self.client.beta.threads.messages.create(thread_id=thread_id,
                                                 role="user", content=ctx_msg)
        run = self.client.beta.threads.runs.create(thread_id=thread_id,
                                                   assistant_id=ASSISTANT_IDS[agent])

        while run.status in ("queued", "in_progress"):
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(thread_id=thread_id,
                                                         run_id=run.id)

        if run.status == "requires_action":
            tcalls = run.required_action.submit_tool_outputs.tool_calls
            outs   = []
            os.makedirs(self.pending_dir(email), exist_ok=True)
            for tc in tcalls:
                args = json.loads(tc.function.arguments)
                save_json(self.pending_path(email, agent),
                          {"agent": agent, "payload": args,
                           "processed": False, "timestamp": time.time()})
                outs.append({"tool_call_id": tc.id,
                             "output": json.dumps({"status": "saved"})})
            self.client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id,
                                                              run_id=run.id,
                                                              tool_outputs=outs)
            self.mark_agent_complete(email, agent)
            self.mark_agent_complete_and_check(email)
            self.transition(email, ClaimStage.REVIEW)
            return

        if run.status == "completed":
            msg = self.client.beta.threads.messages.list(thread_id=thread_id,
                                                         order="desc",
                                                         limit=1).data[0].content[0].text.value
            self.save_agent_message(email, agent, msg)
            try:
                json.loads(msg)   # structured – ignore follow-up
            except json.JSONDecodeError:
                self.save_follow_up(email, agent, msg)

    def agents_to_run(self, email):
        c = self.claim(email)
        return [INCIDENT_TYPE_TO_AGENT[i] for i in c["incident_types"]
                if INCIDENT_TYPE_TO_AGENT[i] not in c["completed_agents"]]

    # ---------------- orchestrate ----------------------
    def orchestrate(self, sender_email: str, user_msg: str,
                    attachments: List[str], claim_id: str = None):
        """
        Main orchestration method for claim processing.
        
        Args:
            sender_email: The email address of the claim submitter
            user_msg: The user's message content
            attachments: List of attachment file paths
            claim_id: Optional existing claim ID (for follow-ups)
        """
        print(f"\n{'='*80}")
        print(f"[ORCHESTRATOR] Starting claim processing for email: {sender_email}")
        if user_msg:
            print(f"[ORCHESTRATOR] User message: {user_msg[:200]}...")
        if attachments:
            print(f"[ORCHESTRATOR] Attachments: {attachments}")
        print(f"{'='*80}\n")
        
        # Generate claim ID if not provided
        if not claim_id:
            claim_id = f"CLM-{int(time.time())}"
            print(f"[ORCHESTRATOR] Generated new claim ID: {claim_id}")
        
        # Initialize claim and context
        self.init_claim(claim_id)
        self.init_context(claim_id)
        
        # Get the claim and ensure it has a stage
        claim = self.claim(claim_id)
        if 'stage' not in claim:
            print(f"[ORCHESTRATOR] Initializing new claim stage")
            claim['stage'] = ClaimStage.NEW
            claim['sender_email'] = sender_email  # Store sender email with claim
            self.save_claim(claim_id, claim)
            
            # Ensure claim exists in database
            try:
                from .db_helper import get_or_create_claim
                claim_data = {
                    'claim_id': claim_id,
                    'sender_email': sender_email,
                    'description': user_msg[:500] if user_msg else 'New claim',
                    'status': 'New',
                    'claim_status': 'Pending'
                }
                db_claim, created = get_or_create_claim(claim_data)
                print(f"[ORCHESTRATOR] {'Created' if created else 'Found'} claim in database: {db_claim.claim_id}")
            except Exception as e:
                print(f"[ORCHESTRATOR ERROR] Failed to create claim in database: {str(e)}")

        # REVIEW stage first
        if claim["stage"] == ClaimStage.REVIEW:
            self.run_review_stage(claim_id)

        # update context
        self.update_context(claim_id, user_msg, attachments)
        if attachments:
            generate_attachment_details(claim_id, attachments)
            self.update_context(claim_id, "", [])

        claim = self.claim(claim_id)
        stage = claim["stage"]

        if stage == ClaimStage.NEW:
            run_clarifying_question(claim_id, user_msg)
            self.transition(claim_id, ClaimStage.QUESTIONED)

        elif stage == ClaimStage.QUESTIONED:
            triage = run_triage(
                claim_id,
                load_json(self.fpath(claim_id, CONTEXT_FILE))["conversation_history"]
            )
            if triage:
                claim["incident_types"] = triage["incident_types"]
                self.save_claim(claim_id, claim)
                self.transition(claim_id, ClaimStage.AGENTS_RUNNING)
                stage = ClaimStage.AGENTS_RUNNING        

        # if stage == ClaimStage.AGENTS_RUNNING:
        #     agents = self.agents_to_run(email)
        #     if user_msg.strip():
        #         for a in agents:
        #             self.save_agent_message(email, a, user_msg, role="user")
        #     for a in agents:
        #         self.run_assistant(email, a)

        #     follow_path = self.fpath(email, FOLLOW_UP_FILE)
        #     if os.path.exists(follow_path):
        #         if run_follow_up_agent(email):
        #             self.transition(email, ClaimStage.FOLLOWUP_REQUESTED)
        #     elif not self.agents_to_run(email):
        #         self.transition(email, ClaimStage.AGENTS_COMPLETE)


        if stage == ClaimStage.AGENTS_RUNNING:
            agents = self.agents_to_run(email)
            if user_msg.strip():
                for a in agents:
                    self.save_agent_message(email, a, user_msg, role="user")

            if agents:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=min(5, len(agents))) as executor:
                    futures = [executor.submit(self.run_assistant, email, a) for a in agents]
                    for fut in as_completed(futures):
                        try:
                            fut.result()
                        except Exception as e:
                            print(f"[orchestrate] Agent error: {e}")

            follow_path = self.fpath(email, FOLLOW_UP_FILE)
            if os.path.exists(follow_path):
                if run_follow_up_agent(email):
                    self.transition(email, ClaimStage.FOLLOWUP_REQUESTED)
            elif not self.agents_to_run(email):
                self.transition(email, ClaimStage.AGENTS_COMPLETE)

        elif stage == ClaimStage.FOLLOWUP_REQUESTED:
            # if user_msg.strip():
            #     agents = self.agents_to_run(email)
            #     for a in agents:
            #         self.save_agent_message(email, a, user_msg, role="user")
            #     for a in agents:
            #         self.run_assistant(email, a)

            #     follow_path = self.fpath(email, FOLLOW_UP_FILE)
            #     if os.path.exists(follow_path):
            #         if not run_follow_up_agent(email):
            #             self.transition(email, ClaimStage.AGENTS_RUNNING)
            #     else:
            #         self.transition(email, ClaimStage.AGENTS_RUNNING)

            if user_msg.strip():
                agents = self.agents_to_run(email)
                for a in agents:
                    self.save_agent_message(email, a, user_msg, role="user")
                
                if agents:
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    with ThreadPoolExecutor(max_workers=min(5, len(agents))) as executor:
                        futures = [executor.submit(self.run_assistant, email, a) for a in agents]
                        for fut in as_completed(futures):
                            try:
                                fut.result()
                            except Exception as e:
                                print(f"[orchestrate][FOLLOWUP_REQUESTED] Agent error: {e}")
                
                follow_path = self.fpath(email, FOLLOW_UP_FILE)
                if os.path.exists(follow_path):
                    if not run_follow_up_agent(email):
                        self.transition(email, ClaimStage.AGENTS_RUNNING)
                else:
                    self.transition(email, ClaimStage.AGENTS_RUNNING)

            elif stage == ClaimStage.AGENTS_COMPLETE:
                self.transition(email, ClaimStage.COMPLETE)

            return True


# Module-level helper for external import
orchestrator = Orchestrator()

def orchestrate(sender_email: str, user_message: str, attachments: List[str], claim_id: str = None):
    """
    Module-level wrapper for the orchestrator.
    
    Args:
        sender_email: The email address of the claim submitter
        user_message: The user's message
        attachments: List of attachment file paths
        claim_id: Optional existing claim ID (for follow-ups)
    """
    global orchestrator
    return orchestrator.orchestrate(sender_email, user_message, attachments, claim_id)