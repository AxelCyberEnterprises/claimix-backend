import os
import sys
import django
from django.db import transaction

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'claimix.settings')
django.setup()

from claim.models import Claim
from policy_holder.models import Policy, PolicyHolder

def get_or_create_claim(claim_data):
    """
    Create or update a claim in the database based on file system data.
    
    Args:
        claim_data (dict): Dictionary containing claim information from file system
        
    Returns:
        tuple: (claim_object, created) - The claim object and a boolean indicating if it was created
    """
    print(f"[DB] Attempting to get or create claim with data: {claim_data}")
    try:
        with transaction.atomic():
            # Extract claim ID from the claim data
            claim_id = claim_data.get('claim_id')
            if not claim_id:
                raise ValueError("Claim ID is required")
            
            # Check if claim already exists
            print(f"[DB] Checking for existing claim with ID: {claim_id}")
            
            # Get current time for default values
            from django.utils import timezone
            from datetime import time as datetime_time
            
            now = timezone.now()
            
            # Get the model's field names to ensure we only include valid fields
            from claim.models import Claim
            model_fields = [f.name for f in Claim._meta.get_fields()]
            
            # Prepare default values for all required fields
            defaults = {
                'description': claim_data.get('description', 'New claim'),
                'incident_date': claim_data.get('incident_date', now.date()),
                'incident_time': claim_data.get('incident_time', datetime_time(0, 0)),  # Default to midnight
                'location': claim_data.get('location', 'Not specified'),
                'status': 'New',
                'created_at': now,
                'updated_at': now,
            }
            
            # Add sender_email if it exists in claim_data and is a valid field
            if 'sender_email' in claim_data and 'sender_email' in model_fields:
                defaults['sender_email'] = claim_data['sender_email']
            
            # Only include fields that exist in the model
            defaults = {k: v for k, v in defaults.items() if k in model_fields}
            
            print(f"[DB] Creating/updating claim with data: {defaults}")
            
            # First try to get existing claim
            try:
                claim = Claim.objects.get(claim_id=claim_id)
                print(f"[DB] Found existing claim: {claim}")
                created = False
                # Update existing claim
                for key, value in defaults.items():
                    setattr(claim, key, value)
                claim.save()
            except Claim.DoesNotExist:
                print("[DB] Creating new claim")
                # Create new claim
                claim = Claim(claim_id=claim_id, **defaults)
                claim.save()
                created = True
            
            # If claim already exists, update it
            if not created:
                print(f"[DB] Updating existing claim: {claim_id}")
                claim.description = claim_data.get('description', claim.description)
                if 'incident_date' in claim_data:
                    claim.incident_date = claim_data['incident_date']
                if 'incident_time' in claim_data:
                    claim.incident_time = claim_data['incident_time']
                if 'location' in claim_data:
                    claim.location_of_incident = claim_data['location']
                if 'sender_email' in claim_data and hasattr(claim, 'sender_email'):
                    claim.sender_email = claim_data['sender_email']
                claim.save()
            
            return claim, created
            
    except Exception as e:
        print(f"[DB ERROR] Failed to create/update claim {claim_id}: {str(e)}")
        raise

def update_claim_stage(claim_id, stage, additional_data=None):
    """
    Update the stage and additional data for a claim.
    
    Args:
        claim_id (str): The claim ID to update
        stage (str): The new stage of the claim
        additional_data (dict, optional): Additional data to update
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    print(f"[DB] Updating claim {claim_id} to stage: {stage}")
    if additional_data:
        print(f"[DB] Additional update data: {additional_data}")
    try:
        with transaction.atomic():
            claim = Claim.objects.get(claim_id=claim_id)
            
            # Get the model's field names to ensure we only update valid fields
            model_fields = [f.name for f in claim._meta.get_fields()]
            
            # Update status field if it exists in the model
            if 'status' in model_fields:
                claim.status = stage
            
            # Update additional fields if provided
            if additional_data:
                for field, value in additional_data.items():
                    if field in model_fields:
                        setattr(claim, field, value)
            
            claim.save()
            return True
            
    except Claim.DoesNotExist:
        print(f"[DB ERROR] Claim {claim_id} not found")
        return False
    except Exception as e:
        print(f"[DB ERROR] Failed to update claim {claim_id}: {str(e)}")
        return False

def get_claim_context(claim_id):
    """
    Retrieve claim context from the database.
    
    Args:
        claim_id (str): The claim ID to retrieve
        
    Returns:
        dict: Claim context data or None if not found
    """
    print(f"[DB] Retrieving context for claim: {claim_id}")
    try:
        claim = Claim.objects.select_related('policy_holder', 'policy').get(claim_id=claim_id)
        return {
            'claim_id': claim.claim_id,
            'sender_email': claim.sender_email if hasattr(claim, 'sender_email') else None,
            'status': claim.status,
            'description': claim.description,
            'incident_date': claim.incident_date,
            'incident_time': claim.incident_time,
            'location': claim.location_of_incident,
            'policy_holder': {
                'id': claim.policy_holder.id if claim.policy_holder else None,
                'name': claim.policy_holder.full_name if claim.policy_holder else 'Unknown',
            },
            'policy': {
                'id': claim.policy.id if claim.policy else None,
                'policy_id': claim.policy.policy_id if claim.policy else 'Unknown',
            },
            'created_at': claim.created_at,
            'updated_at': claim.updated_at,
        }
    except Claim.DoesNotExist:
        return None
    except Exception as e:
        print(f"[DB ERROR] Failed to retrieve claim {claim_id}: {str(e)}")
        return None
