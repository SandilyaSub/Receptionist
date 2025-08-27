"""
Function handlers for Gemini Live API function calling in the connect-service module.
This file contains the implementation of handlers for functions defined in function_definitions.py.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from google.genai import types

# Import Supabase client
import sys
import os

# Add parent directory to path to import supabase_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from supabase_client import get_supabase_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("connect_service.function_handlers")

class FunctionHandlers:
    """
    Class to handle function calls from Gemini Live API.
    Each function defined in function_definitions.py has a corresponding handler method here.
    """
    
    def __init__(self, session=None):
        """
        Initialize the function handlers with an optional Gemini session.
        
        Args:
            session: The Gemini session to use for sending responses back to the model
        """
        self.session = session
        self.call_ended = False
        
    def set_session(self, session):
        """
        Set the Gemini session for sending responses.
        
        Args:
            session: The Gemini session to use
        """
        self.session = session
        
    def is_call_ended(self) -> bool:
        """
        Check if the call has been ended by a function handler.
        
        Returns:
            bool: True if the call has been ended, False otherwise
        """
        return self.call_ended
        
    async def call_handover_function(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the call_handover_function function call.
        
        Args:
            params: Parameters for the function call
                - customer_request: The customer's request that triggered the transfer
                - handover_reason: The reason for transferring to a manager
                - department: The department to transfer to
                - number: The phone number to transfer to
                - backup_department: Optional backup department if primary is unavailable
                - backup_number: Optional backup phone number if primary is unavailable
        
        Returns:
            Dict[str, Any]: Result of the function call
        """
        try:
            # Extract parameters
            customer_request = params.get('customer_request', '')
            handover_reason = params.get('handover_reason', 'Escalation')
            department = params.get('department', 'Manager')
            number = params.get('number', '')
            backup_department = params.get('backup_department', '')
            backup_number = params.get('backup_number', '')
            
            logger.info(f"Call handover requested. Department: {department}, Reason: {handover_reason}")
            logger.info(f"Customer request: {customer_request}")
            
            # Prepare handover data that will be used by the external system (Exotel)
            handover_data = {
                'handover_requested': 'Yes',
                'handover_phrase_used': customer_request,
                'handover_reason': handover_reason,
                'handover_to': [department],
                'handover_numbers': [number]
            }
            
            # Add backup department and number if provided
            if backup_department and backup_number:
                handover_data['handover_to'].append(backup_department)
                handover_data['handover_numbers'].append(backup_number)
                logger.info(f"Backup handover: {backup_department}")
            
            # Store handover data synchronously
            if hasattr(self.session, 'call_sid'):
                # Use direct call instead of creating a task
                storage_result = self.store_handover_data(self.session.call_sid, handover_data)
                logger.info(f"Handover data storage result: {storage_result}")
            else:
                logger.error(f"Session does not have call_sid attribute. Session type: {type(self.session)}")
            
            # If we have a session, send a response to the user
            if self.session:
                response_text = f"I'm transferring your call to our {department} who can better assist you with this. Please hold while I connect you."
                await self.session.send_client_content(turns={"parts": [{"text": response_text}]})
                
                # Set the call as ended to stop the audio loop
                self.call_ended = True
                
                return {
                    "success": True, 
                    "message": f"Call transferred to {department}", 
                    "handover_data": handover_data
                }
            else:
                logger.error("Session not available for call_handover_function")
                return {"success": False, "message": "Session not available"}
                
        except Exception as e:
            logger.error(f"Error in call_handover_function: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}    
            
    def store_handover_data(self, call_sid: str, handover_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store handover data in the database for the given call SID.
        
        Args:
            call_sid: The call SID to associate the handover data with
            handover_data: The handover data to store
        """
        try:
            logger.info(f"Storing handover data for call SID: {call_sid}")
            
            # Get Supabase client
            supabase = get_supabase_client()
            
            # Update call_details table with handover data
            response = supabase.table('call_details').update({
                'call_handover_details': json.dumps(handover_data)
            }).eq('call_sid', call_sid).execute()
            
            if hasattr(response, 'data') and response.data:
                logger.info(f"Successfully stored handover data for call SID: {call_sid}")
            else:
                logger.warning(f"No records updated when storing handover data for call SID: {call_sid}")
                
        except Exception as e:
            logger.error(f"Error storing handover data: {str(e)}")
            # Return error information
            return {"success": False, "error": str(e)}
            
        # Return success if no exceptions
        return {"success": True}

# For testing purposes
if __name__ == "__main__":
    handlers = FunctionHandlers()
    print("Function handlers initialized for testing")
