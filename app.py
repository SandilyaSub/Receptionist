"""
Main Flask Application for Receptionist AI

This application serves both the main WebSocket bridge and the Exotel Connect handler
for human agent handover functionality.
"""

import logging
import asyncio
from flask import Flask
from exotel_connect_handler import ExotelConnectHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_app():
    """Create and configure the Flask application."""
    
    # Create the connect handler
    connect_handler = ExotelConnectHandler()
    
    # Get the Flask app from the connect handler
    app = connect_handler.create_flask_app()
    
    # Add any additional routes or configuration here
    @app.route('/health', methods=['GET'])
    def health_check():
        """General health check endpoint."""
        return {"status": "healthy", "service": "receptionist-ai"}
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)
