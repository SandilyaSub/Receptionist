"""
Exotel Connect Handler for Programmable Connect Applet

This module provides the URL endpoint that Exotel's Connect applet calls
to get phone numbers for call handover to human agents.
"""

import logging
import json
import asyncio
import os
import sys
from typing import Dict, Optional
from flask import Flask, request, jsonify

# Add parent directory to path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handover_service import HandoverService

class ExotelConnectHandler:
    """Handler for Exotel Connect applet dynamic URL requests."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def create_flask_app(self) -> Flask:
        """Create Flask app with connect endpoint."""
        app = Flask(__name__)
        
        @app.route('/exotel/connect', methods=['GET'])
        def handle_connect_request():
            """
            Handle Exotel Connect applet requests - simplified hardcoded response.
            """
            try:
                # Log the incoming request
                call_sid = request.args.get('CallSid', 'unknown')
                call_from = request.args.get('CallFrom')
                call_to = request.args.get('CallTo')
                direction = request.args.get('Direction')
                
                self.logger.info(f"Connect request received - CallSid: {call_sid}, From: {call_from}, To: {call_to}, Direction: {direction}")
                
                # Always return hardcoded response
                response = {
                    "fetch_after_attempt": False,
                    "destination": {
                        "numbers": ["+919901678665"]
                    },
                    "record": True,
                    "recording_channels": "dual"
                }
                
                self.logger.info(f"Returning hardcoded connect response: {response}")
                return jsonify(response), 200
                
            except Exception as e:
                self.logger.error(f"Error handling connect request: {e}")
                # Return hardcoded response even on error
                return jsonify({
                    "fetch_after_attempt": False,
                    "destination": {
                        "numbers": ["+919901678665"]
                    },
                    "record": True,
                    "recording_channels": "dual"
                }), 200
        
        @app.route('/exotel/connect/health', methods=['GET'])
        def health_check():
            """Health check endpoint for the connect handler."""
            return jsonify({"status": "healthy", "service": "exotel-connect-handler"})
        
        @app.route('/connect', methods=['POST'])
        def connect():
            """
            Handle Exotel connect requests and return hardcoded handover response.
            
            Simplified version that always returns the same response for testing.
            """
            try:
                # Get request data for logging
                data = request.get_json() or {}
                call_sid = data.get('CallSid', 'unknown')
                
                self.logger.info(f"Connect request received for CallSid: {call_sid}")
                self.logger.info(f"Request data: {data}")
                
                # Always return hardcoded response
                response = {
                    "fetch_after_attempt": False,
                    "destination": {
                        "numbers": ["+919901678665"]
                    },
                    "record": True,
                    "recording_channels": "dual"
                }
                
                self.logger.info(f"Returning hardcoded connect response: {response}")
                return jsonify(response), 200
                
            except Exception as e:
                self.logger.error(f"Error in connect handler: {e}")
                # Return hardcoded response even on error
                return jsonify({
                    "fetch_after_attempt": False,
                    "destination": {
                        "numbers": ["+919901678665"]
                    },
                    "record": True,
                    "recording_channels": "dual"
                }), 200
        
        return app
    
    def _extract_tenant_from_number(self, phone_number: str) -> str:
        """
        Extract tenant from phone number or return default.
        
        Args:
            phone_number: The phone number to analyze
            
        Returns:
            Tenant name
        """
        # This is a placeholder - implement based on your tenant-to-number mapping
        # For now, return default tenant
        return 'bakery'
    
    def _create_connect_response(self, handover_details: Dict) -> Dict:
        """
        Create Exotel Connect applet response format.
        
        Args:
            handover_details: Handover details from database
            
        Returns:
            Formatted response for Exotel Connect applet
        """
        handover_number = handover_details.get('handover_number')
        handover_reason = handover_details.get('handover_reason', 'escalation')
        
        # Create the response according to Exotel documentation
        response = {
            "fetch_after_attempt": False,
            "destination": {
                "numbers": [handover_number]
            },
            "record": True,
            "recording_channels": "dual",
            "max_ringing_duration": 45,
            "max_conversation_duration": 3600,
            "music_on_hold": {
                "type": "operator_tone"
            }
        }
        
        # Add start call playback based on handover reason
        playback_message = self._get_playback_message(handover_reason)
        if playback_message:
            response["start_call_playback"] = {
                "playback_to": "callee",
                "type": "text",
                "value": playback_message
            }
        
        return response
    
    def _get_playback_message(self, handover_reason: str) -> Optional[str]:
        """
        Get appropriate playback message for the agent based on handover reason.
        
        Args:
            handover_reason: Reason for handover
            
        Returns:
            Message to play to the agent
        """
        messages = {
            'escalation': "You have an escalated call from our AI assistant. The customer requested to speak with a manager.",
            'connect_to_manager': "You have a call transfer from our AI assistant. The customer requested to speak with a manager.",
            'could_not_answer': "You have a call transfer from our AI assistant. The customer had a query that required human assistance.",
            'emergency': "URGENT: You have an emergency call transfer from our AI assistant. Please handle immediately."
        }
        
        return messages.get(handover_reason, "You have a call transfer from our AI assistant.")

# Standalone Flask app for testing
if __name__ == '__main__':
    handler = ExotelConnectHandler()
    app = handler.create_flask_app()
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
