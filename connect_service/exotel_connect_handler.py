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
            Handle Exotel Connect applet requests - 4-case dynamic response logic.
            """
            try:
                # Log the incoming request
                call_sid = request.args.get('CallSid', 'unknown')
                call_from = request.args.get('CallFrom')
                call_to = request.args.get('CallTo')
                direction = request.args.get('Direction')
                
                self.logger.info(f"Connect request received - CallSid: {call_sid}, From: {call_from}, To: {call_to}, Direction: {direction}")
                
                # Get handover result with 4-case logic
                result = self.get_handover_numbers(call_sid)
                
                # Build response based on case
                if result['http_code'] == 404:
                    # Case 2: Call_sid not found
                    self.logger.info(f"Returning 404 for call_sid: {call_sid}")
                    return jsonify({"error": "Call not found"}), 404
                
                # Cases 1, 3, 4: All return 200 with different configurations
                response = {
                    "fetch_after_attempt": result['fetch_after_attempt'],
                    "record": True,
                    "recording_channels": "dual"
                }
                
                # Only add destination if we have numbers (Case 4)
                if result['numbers'] and len(result['numbers']) > 0:
                    response["destination"] = {
                        "numbers": result['numbers']
                    }
                
                self.logger.info(f"Returning {result['status']} response: {response}")
                return jsonify(response), result['http_code']
                
            except Exception as e:
                self.logger.error(f"Unexpected error handling connect request: {e}")
                # Case 1: Unexpected error - retry
                return jsonify({
                    "fetch_after_attempt": True,
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
            Handle Exotel connect requests - 4-case dynamic response logic.
            
            Alternative POST endpoint with same 4-case logic as GET endpoint.
            """
            try:
                # Get request data for logging
                data = request.get_json() or {}
                call_sid = data.get('CallSid', 'unknown')
                
                self.logger.info(f"Connect request received for CallSid: {call_sid}")
                self.logger.info(f"Request data: {data}")
                
                # Get handover result with 4-case logic
                result = self.get_handover_numbers(call_sid)
                
                # Build response based on case
                if result['http_code'] == 404:
                    # Case 2: Call_sid not found
                    self.logger.info(f"Returning 404 for call_sid: {call_sid}")
                    return jsonify({"error": "Call not found"}), 404
                
                # Cases 1, 3, 4: All return 200 with different configurations
                response = {
                    "fetch_after_attempt": result['fetch_after_attempt'],
                    "record": True,
                    "recording_channels": "dual"
                }
                
                # Only add destination if we have numbers (Case 4)
                if result['numbers'] and len(result['numbers']) > 0:
                    response["destination"] = {
                        "numbers": result['numbers']
                    }
                
                self.logger.info(f"Returning {result['status']} response: {response}")
                return jsonify(response), result['http_code']
                
            except Exception as e:
                self.logger.error(f"Unexpected error in connect handler: {e}")
                # Case 1: Unexpected error - retry
                return jsonify({
                    "fetch_after_attempt": True,
                    "record": True,
                    "recording_channels": "dual"
                }), 200
        
        return app
    
    def get_handover_numbers(self, call_sid: str) -> dict:
        """
        Get handover numbers from database for the given call_sid.
        
        Args:
            call_sid: The call session ID from Exotel
            
        Returns:
            Dict with 'status', 'numbers', and 'http_code' keys indicating the response type
        """
        try:
            # Case 1: Supabase connection error - retry with fetch_after_attempt=true
            if not self.supabase:
                self.logger.error("Supabase client not available - connection error")
                return {
                    'status': 'connection_error',
                    'numbers': [],
                    'http_code': 200,
                    'fetch_after_attempt': True
                }
                
            # Query the call_details table for handover details
            response = self.supabase.table('call_details').select('call_handover_details').eq('call_sid', call_sid).execute()
            
            # Case 2: Call_sid not found - 404 Not Found
            if not response.data or len(response.data) == 0:
                self.logger.warning(f"Call_sid not found in database: {call_sid}")
                return {
                    'status': 'call_sid_not_found',
                    'numbers': [],
                    'http_code': 404,
                    'fetch_after_attempt': False
                }
                
            handover_details_json = response.data[0].get('call_handover_details')
            
            # Case 3: Call_sid exists but handover_details is empty/null
            if not handover_details_json:
                self.logger.info(f"Call_sid exists but handover_details is empty: {call_sid}")
                return {
                    'status': 'empty_handover_details',
                    'numbers': [],
                    'http_code': 200,
                    'fetch_after_attempt': False
                }
                
            # Parse the JSON handover details
            try:
                if isinstance(handover_details_json, str):
                    handover_details = json.loads(handover_details_json)
                else:
                    handover_details = handover_details_json
            except json.JSONDecodeError as e:
                self.logger.warning(f"Invalid JSON in handover_details for call_sid {call_sid}: {e}")
                return {
                    'status': 'invalid_handover_data',
                    'numbers': [],
                    'http_code': 200,
                    'fetch_after_attempt': False
                }
                
            # Extract handover numbers
            handover_numbers = handover_details.get('handover_numbers', [])
            
            # Case 3: Call_sid exists but handover_numbers is empty
            if not handover_numbers or len(handover_numbers) == 0:
                self.logger.info(f"Call_sid exists but handover_numbers is empty: {call_sid}")
                return {
                    'status': 'empty_handover_numbers',
                    'numbers': [],
                    'http_code': 200,
                    'fetch_after_attempt': False
                }
            
            # Case 4: Call_sid exists with valid handover_numbers
            self.logger.info(f"Found {len(handover_numbers)} handover numbers for call_sid: {call_sid}")
            return {
                'status': 'success',
                'numbers': handover_numbers,
                'http_code': 200,
                'fetch_after_attempt': False
            }
                
        except Exception as e:
            # Case 1: Unexpected database error - retry with fetch_after_attempt=true
            self.logger.error(f"Database error retrieving handover numbers for call_sid {call_sid}: {e}")
            return {
                'status': 'database_error',
                'numbers': [],
                'http_code': 200,
                'fetch_after_attempt': True
            }

# Standalone Flask app for testing
if __name__ == '__main__':
    handler = ExotelConnectHandler()
    app = handler.create_flask_app()
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
