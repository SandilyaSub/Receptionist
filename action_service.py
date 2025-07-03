"""
Action Service for Receptionist AI

This module handles post-call actions like sending notifications
via WhatsApp using MSG91 API.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from msg91_provider import MSG91Provider
from supabase_client import get_supabase_client

class ActionService:
    def __init__(self, logger=None):
        """Initialize the Action Service with providers and configuration."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize MSG91 provider with credentials from environment
        auth_key = os.getenv("MSG91_AUTH_KEY")
        integrated_number = os.getenv("MSG91_INTEGRATED_NUMBER", "15557892623")  # Default from example
        
        if not auth_key:
            self.logger.warning("MSG91_AUTH_KEY not found in environment variables")
            
        self.msg91_provider = MSG91Provider(
            auth_key=auth_key,
            integrated_number=integrated_number,
            logger=self.logger
        )
        
        # Default owner phone (can be overridden per tenant later)
        self.owner_phone = os.getenv("OWNER_PHONE", "+919482743864")  # Default from spec
        
        # Initialize Supabase client
        self.supabase = get_supabase_client()
    
    async def process_call_actions(self, call_sid: str, tenant_id: str) -> bool:
        """
        Main entry point - process all actions for a completed call
        
        Args:
            call_sid: The Exotel call SID
            tenant_id: The tenant identifier (e.g., 'bakery', 'saloon')
            
        Returns:
            bool: True if all actions were processed successfully, False otherwise
        """
        try:
            self.logger.info(f"Processing actions for call {call_sid}, tenant: {tenant_id}")
            
            # 1. Fetch call details from database
            call_details = await self._fetch_call_details(call_sid)
            if not call_details:
                self.logger.error(f"No call details found for call_sid: {call_sid}")
                return False
                
            # 2. Format customer phone (from_number with +91 prefix)
            customer_phone = self._format_phone_number(call_details.get("from_number"))
            if not customer_phone:
                self.logger.error(f"Invalid customer phone number for call_sid: {call_sid}")
                return False
            
            # 3. Extract message content
            message_data = {
                "call_type": call_details.get("call_type", "Unknown"),
                "details": call_details.get("critical_call_details", "No details available")
            }
            
            self.logger.info(f"Sending notifications for {call_sid} - Type: {message_data['call_type']}")
            
            # 4. Send messages (in parallel)
            results = await asyncio.gather(
                self._send_customer_notification(customer_phone, message_data, tenant_id),
                self._send_owner_notification(self.owner_phone, message_data, customer_phone, tenant_id),
                return_exceptions=True
            )
            
            # Check for exceptions in results
            success = all(isinstance(r, bool) and r for r in results)
            
            # 5. Log action results to database
            await self._log_notification_results(call_sid, results)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing actions for call {call_sid}: {str(e)}")
            return False
    
    async def _fetch_call_details(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch call details from Supabase
        
        Args:
            call_sid: The Exotel call SID
            
        Returns:
            Dict containing call details or None if not found
        """
        try:
            # Query the call_details table for the given call_sid
            call_details_response = self.supabase.table("call_details").select("*").eq("call_sid", call_sid).execute()
            call_details_data = await call_details_response
            
            if call_details_data and hasattr(call_details_data, 'data') and len(call_details_data.data) > 0:
                self.logger.info(f"Found call details in call_details table for {call_sid}")
                return call_details_data.data[0]
            
            # If not found in call_details, check exotel_call_details for basic info
            self.logger.info(f"No data in call_details, checking exotel_call_details for {call_sid}")
            exotel_details_response = self.supabase.table("exotel_call_details").select("*").eq("call_sid", call_sid).execute()
            exotel_details_data = await exotel_details_response
            
            if exotel_details_data and hasattr(exotel_details_data, 'data') and len(exotel_details_data.data) > 0:
                self.logger.info(f"Found call details in exotel_call_details table for {call_sid}")
                return exotel_details_data.data[0]
            
            self.logger.warning(f"No call details found in any table for {call_sid}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching call details: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
        
    def _format_phone_number(self, phone: Optional[str]) -> Optional[str]:
        """
        Format phone number to E.164 format (+91XXXXXXXXXX)
        
        Args:
            phone: Raw phone number from database
            
        Returns:
            Formatted phone number or None if invalid
        """
        if not phone:
            return None
            
        # Strip any non-digit characters
        digits_only = ''.join(filter(str.isdigit, phone))
        
        # Handle different formats
        if len(digits_only) == 10:
            # 10-digit number, add +91 prefix
            return f"+91{digits_only}"
        elif len(digits_only) > 10:
            # Already has country code, ensure it starts with +
            if digits_only.startswith('91'):
                return f"+{digits_only}"
            else:
                return f"+{digits_only}"
        
        # Invalid format
        return None
        
    async def _send_customer_notification(self, phone: str, data: Dict[str, Any], tenant_id: str) -> bool:
        """
        Send notification to customer
        
        Args:
            phone: Customer's phone number
            data: Message data (call_type, details)
            tenant_id: The tenant identifier
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        self.logger.info(f"Sending customer notification to {phone}")
        
        return await self.msg91_provider.send_message(
            to_number=phone,
            template_name="service_booking",
            template_data=self._prepare_customer_template_data(data, tenant_id)
        )
        
    async def _send_owner_notification(self, phone: str, data: Dict[str, Any], 
                                      customer_phone: str, tenant_id: str) -> bool:
        """
        Send notification to business owner
        
        Args:
            phone: Owner's phone number
            data: Message data (call_type, details)
            customer_phone: Customer's phone number
            tenant_id: The tenant identifier
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        self.logger.info(f"Sending owner notification to {phone} about customer {customer_phone}")
        
        return await self.msg91_provider.send_message(
            to_number=phone,
            template_name="service_booking",
            template_data=self._prepare_owner_template_data(data, customer_phone, tenant_id)
        )
        
    def _prepare_customer_template_data(self, data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Prepare template data for customer message
        
        Args:
            data: Message data (call_type, details)
            tenant_id: The tenant identifier
            
        Returns:
            Dict with template components
        """
        # For now, using a simple format - can be enhanced with tenant-specific templates
        return {
            "body": {
                "type": "text",
                "text": f"Thank you for your call! We've noted your {data['call_type']}. Details: {data['details']}"
            }
        }
        
    def _prepare_owner_template_data(self, data: Dict[str, Any], 
                                    customer_phone: str, tenant_id: str) -> Dict[str, Any]:
        """
        Prepare template data for owner message
        
        Args:
            data: Message data (call_type, details)
            customer_phone: Customer's phone number
            tenant_id: The tenant identifier
            
        Returns:
            Dict with template components
        """
        # For now, using a simple format - can be enhanced with tenant-specific templates
        return {
            "body": {
                "type": "text",
                "text": f"New {data['call_type']} from {customer_phone}. Details: {data['details']}"
            }
        }
        
    async def _log_notification_results(self, call_sid: str, results: list) -> None:
        """
        Log notification results to database
        
        Args:
            call_sid: The Exotel call SID
            results: List of results from sending notifications
        """
        try:
            # Convert results to a simple format for logging
            success_count = sum(1 for r in results if isinstance(r, bool) and r)
            total_count = len(results)
            
            # Log to notifications table
            await self.supabase.table("notifications").insert({
                "call_sid": call_sid,
                "notification_type": "whatsapp",
                "status": "success" if success_count == total_count else "partial_failure",
                "details": json.dumps({
                    "success_count": success_count,
                    "total_count": total_count,
                    "timestamp": str(asyncio.get_event_loop().time())
                })
            }).execute()
            
        except Exception as e:
            self.logger.error(f"Error logging notification results: {str(e)}")
