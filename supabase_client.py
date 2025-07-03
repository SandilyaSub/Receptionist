"""
Supabase Client for Receptionist AI

This module provides a singleton Supabase client for database interactions.
"""

import os
import logging
from typing import Optional
from supabase import create_client, Client

# Global client instance
_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """
    Get or create a Supabase client instance
    
    Returns:
        Supabase Client instance
    
    Raises:
        ValueError: If Supabase URL or key is not configured
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
        
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_API_KEY")
    
    if not supabase_url or not supabase_key:
        logger = logging.getLogger(__name__)
        logger.error("Supabase URL or key not found in environment variables")
        raise ValueError("Supabase URL and key must be set in environment variables")
    
    # Create and return the client
    _supabase_client = create_client(supabase_url, supabase_key)
    return _supabase_client
