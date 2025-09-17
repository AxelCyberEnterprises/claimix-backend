from __future__ import annotations

import json
import os
import time
import threading
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid  # <-- Added for claim ID generation

from openai import OpenAI
from dotenv import load_dotenv

from .utils import (
load_json, save_json, get_session_folder,
load_claim_state, save_claim_state,
get_claim_session_folder,
normalize_subject, subject_fingerprint,
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

# agents & helpers (corrected imports)
from .triage_runner        import run_triage
from .clarifying_question  import run_clarifying_question
from .attachment_details   import generate_attachment_details
from .followup_agent       import run_follow_up_agent
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
    def folder(self, claim_id: str) -> str:
        """Get the session folder path for a claim_id."""
        return get_claim_session_folder(claim_id)
        
    def fpath(self, claim_id: str, fname: str) -> str: 
        return os.path.join(self.folder(claim_id), fname)
        
    def pending_dir(self, claim_id: str) -> str: 
        return os.path.join(self.folder(claim_id), PENDING_DIR)
        
    def pending_path(self, claim_id: str, agent: str) -> str: 
        return os.path.join(self.pending_dir(claim_id), PENDING_FILE_TEMPLATE.format(agent))

    # -------- initial state ---------------
    def init_context(self, claim_id: str) -> None:
        p = self.fpath(claim_id, CONTEXT_FILE)
        if not os.path.exists(p):
            save_json(p, {"conversation_history": [], "attachment_details": {},
                          "last_updated": time.time()})

    def init_claim(self, claim_id: str) -> None:
        """Initialize a new claim with the given claim ID if it doesn't exist."""
        # Create session folder using claim ID
        session_folder = get_claim_session_folder(claim_id)
        os.makedirs(session_folder, exist_ok=True)
        os.makedirs(os.path.join(session_folder, PENDING_DIR), exist_ok=True)
        
        p = os.path.join(session_folder, CLAIM_FILE)
        
        if not os.path.exists(p):
            claim_data = {
                "claim_id": claim_id,
                "stage": ClaimStage.NEW,
                "incident_types": {},
                "agents_run": [],
                "agent_threads": {},
                "completed_agents": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "email": "",
                "subject": "",
                "sender_email": "",
                "subject_fp": None,
                "clarifying_sent": False
            }
            # Save to file system
            print(f"[ORCHESTRATOR] Saving claim data to file: {p}")
            save_json(p, claim_data)
            
            # Create in database (writes preserved)
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
    def claim(self, claim_id: str) -> Dict[str, Any]:
        return load_json(self.fpath(claim_id, CLAIM_FILE))

    def save_claim(self, claim_id: str, data: Dict[str, Any]) -> None:
        save_json(self.fpath(claim_id, CLAIM_FILE), data)

    def transition(self, claim_id: str, new_stage: str, additional_data: Optional[Dict[str, Any]] = None) -> None:
        c = self.claim(claim_id)
        print(f"[ORCHESTRATOR] Attempting to transition claim {c['claim_id']} from {c['stage']} to {new_stage}")
        if new_stage in ClaimStage.VALID_TRANSITIONS.get(c["stage"], []):
            # Update database with new stage (write preserved)
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
            c["updated_at"] = datetime.now().isoformat()
            self.save_claim(claim_id, c)

    def save_follow_up(self, claim_id: str, agent: str, content: str) -> None:
        p = self.fpath(claim_id, FOLLOW_UP_FILE)
        with self._lock:
            d = load_json(p) if os.path.exists(p) else {"responses": []}
            d["responses"].append({"agent": agent, "response": content, "timestamp": time.time()})
            save_json(p, d)

    def overwrite_decision(self, claim_id: str, agent: str, decision: Any) -> None:
        p = self.fpath(claim_id, DECISIONS_FILE)
        with self._lock:
            data = load_json(p) if os.path.exists(p) else []
            data = [d for d in data if d["agent"] != agent]
            data.append({"agent": agent, "decision": decision, "timestamp": time.time()})
            save_json(p, data)

    def _evaluate_pending_file(self, path: str):
        info = load_json(path)
        agent = info["agent"]
        payload = info["payload"]
        if agent not in DECISION_ENGINE:
            return path, agent, None  # unknown agent, skip
        decision = DECISION_ENGINE[agent](payload)
        return path, agent, decision

    def run_assistant(self, claim_id: str, agent: str) -> None:
        if agent not in ASSISTANT_IDS or not ASSISTANT_IDS[agent]:
            print(f"[ORCHESTRATOR] Skipping agent {agent}: missing ASSISTANT_ID")
            return
        claim = self.claim(claim_id)
        thread_id = claim["agent_threads"].get(agent)
        if not thread_id:
            thread_id = self.client.beta.threads.create().id
            claim["agent_threads"][agent] = thread_id
            self.save_claim(claim_id, claim)

        ctx_msg = self.build_context_msg(claim_id)
        self.save_agent_message(claim_id, agent, ctx_msg, role="user")
        self.client.beta.threads.messages.create(thread_id=thread_id, role="user", content=ctx_msg)
        run = self.client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_IDS[agent])

        while run.status in ("queued", "in_progress"):
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

        if run.status == "requires_action":
            tcalls = run.required_action.submit_tool_outputs.tool_calls
            outs = []
            os.makedirs(self.pending_dir(claim_id), exist_ok=True)
            for tc in tcalls:
                args = json.loads(tc.function.arguments)
                save_json(self.pending_path(claim_id, agent),
                          {"agent": agent, "payload": args, "processed": False, "timestamp": time.time()})
                outs.append({"tool_call_id": tc.id, "output": json.dumps({"status": "saved"})})
            self.client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run.id, tool_outputs=outs)
            # Do NOT mark agent complete here!
            self.transition(claim_id, ClaimStage.REVIEW)
            return

        if run.status == "completed":
            msg = self.client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1).data[0].content[0].text.value
            self.save_agent_message(claim_id, agent, msg)
            try:
                json.loads(msg)
            except json.JSONDecodeError:
                self.save_follow_up(claim_id, agent, msg)

    def run_review_stage(self, claim_id: str) -> None:
        pend_dir = self.pending_dir(claim_id)
        if not os.path.isdir(pend_dir):
            return
        pending_paths = [os.path.join(pend_dir, f) for f in os.listdir(pend_dir)
                        if f.endswith("_pending.json")]

        if not pending_paths:
            return

        processed_any = False
        with ThreadPoolExecutor(max_workers=min(5, len(pending_paths))) as ex:
            futures = {ex.submit(self._evaluate_pending_file, p): p for p in pending_paths}
            for fut in as_completed(futures):
                try:
                    path, agent, decision = fut.result()
                except Exception as e:
                    print(f"[run_review_stage] Error evaluating {futures[fut]}: {e}")
                    continue

                if decision is not None:
                    self.overwrite_decision(claim_id, agent, decision)
                    self.mark_agent_complete(claim_id, agent)  # <-- Only mark complete here!
                    processed_any = True

                info = load_json(path)
                info["processed"] = True
                save_json(path, info)
        if processed_any:
            self.transition(claim_id, ClaimStage.AGENTS_RUNNING)

    def build_context_msg(self, claim_id: str) -> str:
        ctx = load_json(self.fpath(claim_id, CONTEXT_FILE), default={}) or {}
        history = ctx.get("conversation_history", []) or []

        out = ""
        for m in history:
            role = (m.get('role') or 'user').upper()
            content = m.get('content') or ''
            out += f"{role}: {content}\n"

        ad_obj = ctx.get("attachment_details") or {}
        details_list = None
        if isinstance(ad_obj, dict):
            details_list = ad_obj.get("attachment_details")

        if isinstance(details_list, list) and details_list:
            out += "\nATTACHMENTS:\n"
            for item in details_list:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", "unknown")
                det = item.get("details", "")
                if det:
                    out += f"{name}: {det}\n"
        elif isinstance(ad_obj, dict) and ad_obj:
            out += "\nATTACHMENTS:\n"
            for k, v in ad_obj.items():
                out += f"{k}: {v}\n"

        return out

    def run_assistant(self, claim_id: str, agent: str) -> None:
        if agent not in ASSISTANT_IDS or not ASSISTANT_IDS[agent]:
            print(f"[ORCHESTRATOR] Skipping agent {agent}: missing ASSISTANT_ID")
            return
        claim = self.claim(claim_id)
        thread_id = claim["agent_threads"].get(agent)
        if not thread_id:
            thread_id = self.client.beta.threads.create().id
            claim["agent_threads"][agent] = thread_id
            self.save_claim(claim_id, claim)

        ctx_msg = self.build_context_msg(claim_id)
        self.save_agent_message(claim_id, agent, ctx_msg, role="user")
        self.client.beta.threads.messages.create(thread_id=thread_id, role="user", content=ctx_msg)
        run = self.client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_IDS[agent])

        while run.status in ("queued", "in_progress"):
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

        if run.status == "requires_action":
            tcalls = run.required_action.submit_tool_outputs.tool_calls
            outs = []
            os.makedirs(self.pending_dir(claim_id), exist_ok=True)
            for tc in tcalls:
                args = json.loads(tc.function.arguments)
                save_json(self.pending_path(claim_id, agent),
                          {"agent": agent, "payload": args, "processed": False, "timestamp": time.time()})
                outs.append({"tool_call_id": tc.id, "output": json.dumps({"status": "saved"})})
            self.client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run.id, tool_outputs=outs)
            # Do NOT mark agent complete here!
            self.transition(claim_id, ClaimStage.REVIEW)
            return

        if run.status == "completed":
            msg = self.client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1).data[0].content[0].text.value
            self.save_agent_message(claim_id, agent, msg)
            try:
                json.loads(msg)
            except json.JSONDecodeError:
                self.save_follow_up(claim_id, agent, msg)

    def agents_to_run(self, claim_id: str) -> List[str]:
        c = self.claim(claim_id)
        return [INCIDENT_TYPE_TO_AGENT[i] for i in c["incident_types"]
                if INCIDENT_TYPE_TO_AGENT[i] not in c["completed_agents"]]
    

    # -------- context helpers -------------
    def update_context(self, claim_id: str, user_msg: str, attachments: Optional[List[str]] = None) -> None:
        print(f"[ORCHESTRATOR] Updating context for claim: {claim_id}")
        msg_text = (user_msg or "")
        if msg_text.strip():
            print(f"[ORCHESTRATOR] Processing user message: {msg_text[:100]}...")
        if attachments:
            print(f"[ORCHESTRATOR] Processing {len(attachments)} attachments")
        """
        Update the conversation context with a new user message and any attachments.
        Also updates the claim in the database if this is new information.
        """
        ctx_path = self.fpath(claim_id, CONTEXT_FILE)

        # Load context safely with defaults
        ctx = load_json(ctx_path, default=None)
        if ctx is None or not isinstance(ctx, dict):
            ctx = {"conversation_history": [], "attachment_details": {}, "last_updated": time.time()}

        claim = self.claim(claim_id)

        # Update file-based context
        if msg_text.strip():
            ctx["conversation_history"].append({
                "role": "user",
                "content": msg_text,
                "timestamp": time.time()
            })

            # If this is the first user message, update the claim description (DB write preserved)
            if len(ctx["conversation_history"]) == 1 and claim.get("stage") == ClaimStage.NEW:
                try:
                    update_claim_stage(
                        claim_id=claim["claim_id"],
                        stage=claim["stage"],
                        additional_data={
                            'description': msg_text[:500],
                            'updated_at': datetime.now()
                        }
                    )
                except Exception as e:
                    print(f"[DB ERROR] Failed to update claim description: {e}")

        # Normalize attachments input
        atts = attachments or []
        if atts:
            ctx["conversation_history"].append({
                "role": "user",
                "content": f"[{len(atts)} attachment(s)]",
                "timestamp": time.time(),
                "attachments": atts
            })

        # Handle attachment details if they exist; keep a dict structure by default
        ad_path = self.fpath(claim_id, ATTACHMENT_DATA_FILE)
        if os.path.exists(ad_path):
            ad = load_json(ad_path, default={}) or {}
            ctx["attachment_details"] = ad

        ctx["last_updated"] = time.time()
        save_json(ctx_path, ctx)

    # -------- message persistence ---------
    def save_agent_message(self, claim_id: str, agent: str, content: str, role: str = "assistant") -> None:
        p = self.fpath(claim_id, f"{agent}_messages.json")
        with self._lock:
            data = load_json(p) if os.path.exists(p) else []
            data.append({"role": role, "content": content, "timestamp": time.time()})
            save_json(p, data)
    
    # -------- agent bookkeeping -----------
    def mark_agent_complete(self, claim_id: str, agent: str) -> None:
        with self._lock:
            claim = self.claim(claim_id)
            done  = claim.get("completed_agents", [])
            if agent not in done:
                done.append(agent)
                claim["completed_agents"] = done
                self.save_claim(claim_id, claim)

    def mark_agent_complete_and_check(self, claim_id: str) -> None:
        with self._lock:
            claim = self.claim(claim_id)
            completed = set(claim.get("completed_agents", []))
            all_agents = set([INCIDENT_TYPE_TO_AGENT[i] for i in claim["incident_types"]])
            # Already up to date?
            if completed == all_agents and claim["stage"] == ClaimStage.AGENTS_RUNNING:
                self.transition(claim_id, ClaimStage.AGENTS_COMPLETE)

    # ---------------- orchestrate ----------------------
    def orchestrate(self, sender_email: str, user_msg: str,
                attachments: List[str],
                claim_id: Optional[str] = None,
                subject: Optional[str] = None):
        """
        Main orchestration method for claim processing.
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
            claim_id = f"CLM-{uuid.uuid4().hex[:10].upper()}"
            print(f"[ORCHESTRATOR] Generated new claim ID: {claim_id}")

        # Initialize claim and context
        self.init_claim(claim_id)
        self.init_context(claim_id)

        # Persist sender_email immediately
        claim = self.claim(claim_id)
        if sender_email and (not claim.get('sender_email') or claim['sender_email'] != sender_email):
            claim['sender_email'] = sender_email
            self.save_claim(claim_id, claim)

        # Persist subject fingerprint on first contact
        if subject:
            claim = self.claim(claim_id)
            if not claim.get("subject_fp"):
                norm = normalize_subject(subject)
                if norm:
                    fp = subject_fingerprint(sender_email, norm)
                    claim["subject_fp"] = fp
                    # Optionally store original normalized subject for reference
                    claim["initial_subject"] = norm
                    self.save_claim(claim_id, claim)

        # REVIEW stage first
        if claim["stage"] == ClaimStage.REVIEW:
            self.run_review_stage(claim_id)

        # update context
        self.update_context(claim_id, user_msg, attachments)
        if attachments:
            generate_attachment_details(claim_id, attachments)
            self.update_context(claim_id, "", [])

        # reload claim after potential updates
        claim = self.claim(claim_id)
        stage = claim["stage"]

        if stage == ClaimStage.NEW:
            # Clarifying should only be sent once
            if not claim.get("clarifying_sent"):
                run_clarifying_question(claim_id, user_msg, sender_email)
                claim["clarifying_sent"] = True
                self.save_claim(claim_id, claim)
                self.transition(claim_id, ClaimStage.QUESTIONED)
            else:
                # Stage regression guard: advance without re-sending
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

        if stage == ClaimStage.AGENTS_RUNNING:
            agents = self.agents_to_run(claim_id)
            if user_msg.strip():
                for a in agents:
                    self.save_agent_message(claim_id, a, user_msg, role="user")

            if agents:
                with ThreadPoolExecutor(max_workers=min(5, len(agents))) as executor:
                    futures = [executor.submit(self.run_assistant, claim_id, a) for a in agents]
                    for fut in as_completed(futures):
                        try:
                            fut.result()
                        except Exception as e:
                            print(f"[orchestrate] Agent error: {e}")

            # Always process pending payloads before checking for completion
            self.run_review_stage(claim_id)

            follow_path = self.fpath(claim_id, FOLLOW_UP_FILE)
            if os.path.exists(follow_path):
                if run_follow_up_agent(claim_id, sender_email):
                    self.transition(claim_id, ClaimStage.FOLLOWUP_REQUESTED)
            elif not self.agents_to_run(claim_id):
                self.transition(claim_id, ClaimStage.AGENTS_COMPLETE)

        elif stage == ClaimStage.FOLLOWUP_REQUESTED:
            if user_msg.strip():
                agents = self.agents_to_run(claim_id)
                for a in agents:
                    self.save_agent_message(claim_id, a, user_msg, role="user")
                
                if agents:
                    with ThreadPoolExecutor(max_workers=min(5, len(agents))) as executor:
                        futures = [executor.submit(self.run_assistant, claim_id, a) for a in agents]
                        for fut in as_completed(futures):
                            try:
                                fut.result()
                            except Exception as e:
                                print(f"[orchestrate][FOLLOWUP_REQUESTED] Agent error: {e}")
                
                follow_path = self.fpath(claim_id, FOLLOW_UP_FILE)
                if os.path.exists(follow_path):
                    if not run_follow_up_agent(claim_id, sender_email):
                        self.transition(claim_id, ClaimStage.AGENTS_RUNNING)
                else:
                    self.transition(claim_id, ClaimStage.AGENTS_RUNNING)

            return True


# Module-level helper for external import
orchestrator = Orchestrator()

def orchestrate(sender_email: str, user_message: str, attachments: List[str], claim_id: str = None, subject: Optional[str] = None):
    """
    Module-level wrapper for the orchestrator.
    
    Args:
        sender_email: The email address of the claim submitter
        user_message: The user's message
        attachments: List of attachment file paths
        claim_id: Optional existing claim ID (for follow-ups)
        subject: Optional subject line of the email
    """
    global orchestrator
    return orchestrator.orchestrate(sender_email, user_message, attachments, claim_id, subject)
