"""
Function handlers for Gemini Live API function calling in the connect-service module.
This file contains the implementation of handlers for functions defined in function_definitions.py.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from google.genai import types

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
        
        Returns:
            Dict[str, Any]: Result of the function call
        """
        try:
            customer_request = params.get('customer_request', '')
            handover_reason = params.get('handover_reason', 'Escalation')
            
            logger.info(f"Transfer to manager requested. Reason: {handover_reason}")
            logger.info(f"Customer request: {customer_request}")
            
            # Prepare handover data that could be used by an external system
            handover_data = {
                'handover_requested': 'Yes',
                'handover_phrase_used': customer_request,
                'handover_reason': handover_reason,
                'handover_to': 'Manager',
                'handover_number': '+919876543210'  # Example manager number
            }
            
            # If we have a session, send a response to the user
            if self.session:
                response_text = "I'm transferring your call to a manager who can better assist you with this. Please hold while I connect you."
                await self.session.send_client_content(turns={"parts": [{"text": response_text}]})
                
                # Set the call as ended to stop the audio loop
                self.call_ended = True
                
                return {
                    "success": True, 
                    "message": "Call transferred to manager", 
                    "handover_data": handover_data
                }
            else:
                logger.error("Session not available for call_handover_function")
                return {"success": False, "message": "Session not available"}
                
        except Exception as e:
            logger.error(f"Error in call_handover_function: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}

# For testing purposes
if __name__ == "__main__":
    handlers = FunctionHandlers()
    print("Function handlers initialized for testing")
