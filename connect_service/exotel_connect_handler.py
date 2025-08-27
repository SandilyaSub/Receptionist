"""
Exotel Connect Handler for Programmable Connect Applet

This module provides the URL endpoint that Exotel's Connect applet calls
to get phone numbers for call handover to human agents.
"""

import logging
import os
import json
from flask import Flask, request, jsonify
from supabase_client import get_supabase_client

class ExotelConnectHandler:
    """Handler for Exotel Connect applet dynamic URL requests."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supabase = get_supabase_client()
        
    def create_flask_app(self) -> Flask:
        """Create Flask app with connect endpoint."""
        app = Flask(__name__)
        
        @app.route('/exotel/connect', methods=['GET'])
        def handle_connect_request():
            """
            Handle Exotel Connect applet requests - dynamic response from database.
            """
            try:
                # Log the incoming request
                call_sid = request.args.get('CallSid', 'unknown')
                call_from = request.args.get('CallFrom')
                call_to = request.args.get('CallTo')
                direction = request.args.get('Direction')
                
                self.logger.info(f"Connect request received - CallSid: {call_sid}, From: {call_from}, To: {call_to}, Direction: {direction}")
                
                # Get dynamic handover numbers from database
                handover_numbers = self.get_handover_numbers(call_sid)
                
                response = {
                    "fetch_after_attempt": False,
                    "destination": {
                        "numbers": handover_numbers
                    },
                    "record": True,
                    "recording_channels": "dual"
                }
                
                self.logger.info(f"Returning dynamic connect response: {response}")
                return jsonify(response), 200
                
            except Exception as e:
                self.logger.error(f"Error handling connect request: {e}")
                # Return fallback response on error
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
            Handle Exotel connect requests and return dynamic handover response.
            
            Alternative POST endpoint that queries database for handover numbers.
            """
            try:
                # Get request data for logging
                data = request.get_json() or {}
                call_sid = data.get('CallSid', 'unknown')
                
                self.logger.info(f"Connect request received for CallSid: {call_sid}")
                self.logger.info(f"Request data: {data}")
                
                # Get dynamic handover numbers from database
                handover_numbers = self.get_handover_numbers(call_sid)
                
                response = {
                    "fetch_after_attempt": False,
                    "destination": {
                        "numbers": handover_numbers
                    },
                    "record": True,
                    "recording_channels": "dual"
                }
                
                self.logger.info(f"Returning dynamic connect response: {response}")
                return jsonify(response), 200
                
            except Exception as e:
                self.logger.error(f"Error in connect handler: {e}")
                # Return fallback response on error
                return jsonify({
                    "fetch_after_attempt": False,
                    "destination": {
                        "numbers": ["+919901678665"]
                    },
                    "record": True,
                    "recording_channels": "dual"
                }), 200
        
        return app
    
    def get_handover_numbers(self, call_sid: str) -> list:
        """
        Get handover numbers from database for the given call_sid.
        
        Args:
            call_sid: The call session ID from Exotel
            
        Returns:
            List of phone numbers for handover, or fallback number if not found
        """
        fallback_numbers = ["+919901678665"]
        
        try:
            if not self.supabase:
                self.logger.warning("Supabase client not available, using fallback numbers")
                return fallback_numbers
                
            # Query the call_details table for handover details
            response = self.supabase.table('call_details').select('call_handover_details').eq('call_sid', call_sid).execute()
            
            if not response.data or len(response.data) == 0:
                self.logger.warning(f"No handover details found for call_sid: {call_sid}, using fallback")
                return fallback_numbers
                
            handover_details_json = response.data[0].get('call_handover_details')
            if not handover_details_json:
                self.logger.warning(f"Empty handover details for call_sid: {call_sid}, using fallback")
                return fallback_numbers
                
            # Parse the JSON handover details
            if isinstance(handover_details_json, str):
                handover_details = json.loads(handover_details_json)
            else:
                handover_details = handover_details_json
                
            # Extract handover numbers
            handover_numbers = handover_details.get('handover_numbers', [])
            
            if handover_numbers and len(handover_numbers) > 0:
                self.logger.info(f"Found {len(handover_numbers)} handover numbers for call_sid: {call_sid}")
                return handover_numbers
            else:
                self.logger.warning(f"No handover numbers in details for call_sid: {call_sid}, using fallback")
                return fallback_numbers
                
        except Exception as e:
            self.logger.error(f"Error retrieving handover numbers for call_sid {call_sid}: {e}")
            return fallback_numbers

# Standalone Flask app for testing
if __name__ == '__main__':
    handler = ExotelConnectHandler()
    app = handler.create_flask_app()
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
