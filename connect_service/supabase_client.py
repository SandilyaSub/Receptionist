"""
Supabase client for connect service database operations.
"""

import os
import logging
from supabase import create_client, Client
from typing import Optional

logger = logging.getLogger(__name__)

def get_supabase_client() -> Optional[Client]:
    """
    Create and return a Supabase client instance.
    
    Returns:
        Supabase client instance or None if configuration is missing
    """
    try:
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_API_KEY')
        
        if not supabase_url or not supabase_key:
            logger.error("Missing Supabase configuration: SUPABASE_URL or SUPABASE_API_KEY")
            return None
            
        return create_client(supabase_url, supabase_key)
        
    except Exception as e:
        logger.error(f"Error creating Supabase client: {e}")
        return None
