"""
Exotel Connect Handler for Programmable Connect Applet

This module provides the URL endpoint that Exotel's Connect applet calls
to get phone numbers for call handover to human agents.
"""

import logging
import os
from flask import Flask, request, jsonify

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

# Standalone Flask app for testing
if __name__ == '__main__':
    handler = ExotelConnectHandler()
    app = handler.create_flask_app()
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
