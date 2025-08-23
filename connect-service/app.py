"""
Connect Handler Service for Railway Deployment

This is a separate Railway service that handles Exotel Connect applet requests
for call handover to human agents.
"""

import os
import sys
import logging
import asyncio
from flask import Flask

# Add parent directory to path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exotel_connect_handler import ExotelConnectHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_app():
    """Create and configure the Flask application for Railway deployment."""
    
    # Create the connect handler
    connect_handler = ExotelConnectHandler()
    
    # Get the Flask app from the connect handler
    app = connect_handler.create_flask_app()
    
    # Add Railway-specific health check
    @app.route('/health', methods=['GET'])
    def railway_health_check():
        """Railway health check endpoint."""
        return {"status": "healthy", "service": "connect-handler", "version": "1.0.0"}
    
    # Add root endpoint for Railway
    @app.route('/', methods=['GET'])
    def root():
        """Root endpoint for Railway service."""
        return {
            "service": "Exotel Connect Handler",
            "status": "running",
            "endpoints": {
                "connect": "/exotel/connect",
                "health": "/health"
            }
        }
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Get port from Railway environment or default to 5001
    port = int(os.environ.get('PORT', 5001))
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False)
