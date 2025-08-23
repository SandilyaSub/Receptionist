"""
Handover Service for Human Agent Escalation

This module handles the detection and processing of call handover requests
from AI to human agents during Gemini Live conversations.
"""

import logging
import json
import re
from typing import Dict, Optional, Tuple
from supabase_client import get_supabase_client

class HandoverService:
    """Service for detecting and processing call handover requests."""
    
    def __init__(self, tenant: str):
        self.tenant = tenant
        self.logger = logging.getLogger(__name__)
        self.supabase = get_supabase_client()
        
        # Handover detection patterns
        self.handover_patterns = {
            'escalation': [
                r'speak.*manager', r'talk.*supervisor', r'escalate', r'higher.*authority',
                r'someone.*senior', r'manager.*please', r'supervisor.*help'
            ],
            'connect_to_manager': [
                r'connect.*manager', r'transfer.*manager', r'manager.*available',
                r'speak.*boss', r'talk.*head', r'branch.*head'
            ],
            'could_not_answer': [
                r'don\'t.*know', r'not.*sure', r'can\'t.*help', r'unable.*assist',
                r'beyond.*scope', r'need.*help', r'complicated.*query'
            ],
            'emergency': [
                r'emergency', r'urgent', r'immediate.*help', r'critical',
                r'ambulance', r'medical.*emergency'
            ],
            'just_hangup': [
                r'goodbye', r'bye', r'thank.*you', r'that\'s.*all',
                r'no.*more.*questions', r'end.*call'
            ]
        }
        
        # Handover destination mapping
        self.handover_destinations = {
            'escalation': 'branch_head',
            'connect_to_manager': 'branch_head', 
            'could_not_answer': 'branch_head',
            'emergency': 'emergency',
            'just_hangup': None
        }

    async def analyze_conversation_for_handover(self, conversation_text: str) -> Dict:
        """
        Analyze conversation text to detect handover requests.
        
        Args:
            conversation_text: Full conversation transcript
            
        Returns:
            Dict containing handover analysis results
        """
        self.logger.info("Analyzing conversation for handover requests")
        
        # Initialize handover details
        handover_details = {
            'handover_requested': 'no',
            'handover_reason': 'just_hangup',
            'handover_to': '',
            'handover_number': ''
        }
        
        if not conversation_text:
            self.logger.warning("No conversation text provided for handover analysis")
            return handover_details
            
        # Convert to lowercase for pattern matching
        text_lower = conversation_text.lower()
        
        # Check for handover patterns
        detected_reason = None
        for reason, patterns in self.handover_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    detected_reason = reason
                    self.logger.info(f"Detected handover pattern: {pattern} -> {reason}")
                    break
            if detected_reason:
                break
        
        # If handover detected, populate details
        if detected_reason and detected_reason != 'just_hangup':
            handover_details['handover_requested'] = 'yes'
            handover_details['handover_reason'] = detected_reason
            handover_details['handover_to'] = self.handover_destinations.get(detected_reason, 'branch_head')
            
            # Get handover number
            handover_number = await self._get_handover_number(handover_details['handover_to'])
            handover_details['handover_number'] = handover_number
            
        self.logger.info(f"Handover analysis result: {handover_details}")
        return handover_details

    async def _get_handover_number(self, handover_to: str) -> str:
        """
        Get the appropriate phone number for handover.
        
        Args:
            handover_to: Type of handover (branch_head, emergency, etc.)
            
        Returns:
            Phone number for handover
        """
        try:
            if handover_to == 'emergency':
                # Return emergency number (could be configurable)
                return '+911080'  # Example emergency number
                
            elif handover_to == 'branch_head':
                # Get branch head number from tenant config
                response = self.supabase.table('tenant_configs').select('branch_head_phone').eq('tenant_name', self.tenant).execute()
                
                if response.data and len(response.data) > 0:
                    branch_head_phone = response.data[0].get('branch_head_phone')
                    if branch_head_phone:
                        self.logger.info(f"Retrieved branch head phone: {branch_head_phone}")
                        return branch_head_phone
                
                # Fallback to environment variable or default
                import os
                fallback_number = os.getenv('DEFAULT_BRANCH_HEAD_PHONE', '+919876543210')
                self.logger.warning(f"No branch head phone found for tenant {self.tenant}, using fallback: {fallback_number}")
                return fallback_number
                
            else:
                self.logger.warning(f"Unknown handover_to type: {handover_to}")
                return ''
                
        except Exception as e:
            self.logger.error(f"Error getting handover number: {e}")
            return ''

    async def save_handover_details(self, call_sid: str, handover_details: Dict) -> bool:
        """
        Save handover details to the database.
        
        Args:
            call_sid: Exotel call SID
            handover_details: Handover details dictionary
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self.logger.info(f"Saving handover details for call_sid: {call_sid}")
            
            # Update call_details table with handover information
            response = self.supabase.table('call_details').update({
                'call_handover_details': handover_details
            }).eq('call_sid', call_sid).execute()
            
            if response.data:
                self.logger.info(f"Successfully saved handover details for call_sid: {call_sid}")
                return True
            else:
                self.logger.error(f"Failed to save handover details for call_sid: {call_sid}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error saving handover details: {e}")
            return False

    async def get_handover_details(self, call_sid: str) -> Optional[Dict]:
        """
        Retrieve handover details for a call.
        
        Args:
            call_sid: Exotel call SID
            
        Returns:
            Handover details dictionary or None if not found
        """
        try:
            response = self.supabase.table('call_details').select('call_handover_details').eq('call_sid', call_sid).execute()
            
            if response.data and len(response.data) > 0:
                handover_details = response.data[0].get('call_handover_details')
                self.logger.info(f"Retrieved handover details for call_sid: {call_sid}")
                return handover_details
            else:
                self.logger.warning(f"No handover details found for call_sid: {call_sid}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error retrieving handover details: {e}")
            return None
