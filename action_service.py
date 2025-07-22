"""
Action Service for Receptionist AI

This module handles post-call actions like sending notifications
via WhatsApp using MSG91 API.
"""

import os
import json
import logging
import asyncio
import time
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional, Callable, List, Union
from msg91_provider import MSG91Provider
from supabase_client import get_supabase_client
from whatsapp_notification_service import WhatsAppNotificationService

def async_retry(max_retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Retry decorator for async functions with exponential backoff
    
    Args:
        max_retries: Maximum number of retries before giving up
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier e.g. value of 2 will double the delay each retry
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get logger from self if available (for class methods)
            logger = args[0].logger if args and hasattr(args[0], 'logger') else logging.getLogger(__name__)
            
            retry_count = 0
            current_delay = delay
            
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error(f"Failed after {max_retries} retries: {str(e)}")
                        return False
                    
                    logger.warning(f"Retry {retry_count}/{max_retries} after error: {str(e)}. Waiting {current_delay}s...")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

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
        
        # Initialize WhatsApp notification service
        self.whatsapp_service = WhatsAppNotificationService(logger=self.logger)
        
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
            
            # 1. Fetch tenant configuration from database
            tenant_config = await self._fetch_tenant_config(tenant_id)
            
            # 2. Fetch call details from database
            call_details = await self._fetch_call_details(call_sid)
            if not call_details:
                self.logger.error(f"No call details found for call_sid: {call_sid}")
                return False
                
            # 3. Format customer phone (from_number with +91 prefix)
            raw_phone = call_details.get("from_number")
            self.logger.info(f"Raw customer phone from database: '{raw_phone}' for call_sid: {call_sid}")
            
            # Debug the call_details structure
            self.logger.info(f"Call details keys: {list(call_details.keys())}")
            
            # Try alternative field names if 'from_number' is not present or empty
            if not raw_phone:
                possible_fields = ["From", "from", "caller", "caller_number", "phone"]
                for field in possible_fields:
                    if field in call_details and call_details[field]:
                        raw_phone = call_details[field]
                        self.logger.info(f"Found phone in alternative field '{field}': {raw_phone}")
            
            customer_phone = self._format_phone_number(raw_phone)
            if not customer_phone:
                self.logger.error(f"Invalid customer phone number for call_sid: {call_sid}")
                return False
            
            # 4. Determine owner phone from tenant config with fallback
            owner_phone = tenant_config.get("branch_head_phone_number")
            if owner_phone:
                self.logger.info(f"Using tenant-specific owner phone: {owner_phone} for tenant: {tenant_id}")
            else:
                owner_phone = self.owner_phone
                self.logger.warning(f"No tenant-specific owner phone found for {tenant_id}, falling back to default: {owner_phone}")
            
            # 5. Send notifications
            results = []
            
            # 5.1 Send customer notification if phone available and call_type is supported
            customer_phone = call_details.get("from_number")
            call_type = call_details.get("call_type", "Unknown")
            
            # Only send notifications for Booking and Informational call types
            if customer_phone and call_type in ["Booking", "Informational"]:
                self.logger.info(f"Sending {call_type} notification to customer {customer_phone}")
                customer_result = await self._send_customer_notification(
                    phone=customer_phone,
                    data={
                        "call_type": call_type,
                        "details": call_details.get("critical_call_details", {}),
                        "critical_call_details": call_details.get("critical_call_details", {})
                    },
                    tenant_id=tenant_id,
                    call_sid=call_sid
                )
                results.append(("customer", customer_result))
            else:
                if not customer_phone:
                    self.logger.warning(f"No customer phone available for call_sid: {call_sid}")
                else:
                    self.logger.info(f"Skipping notification for call_type: {call_type}")
            
            # 5.2 Send owner notification using tenant-specific phone
            owner_result = await self._send_owner_notification(
                phone=owner_phone,  # Now using tenant-specific phone with fallback
                data={
                    "call_type": call_type,
                    "details": call_details.get("critical_call_details", {}),
                    "critical_call_details": call_details.get("critical_call_details", {})
                },
                customer_phone=customer_phone,
                tenant_id=tenant_id,
                return_exceptions=True
            )
            results.append(("owner", owner_result))
            
            # Log notification results
            await self._log_notification_results(call_sid, results)
            
            # Check for exceptions in results
            success = all(isinstance(r, bool) and r for r in results)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing actions for call {call_sid}: {str(e)}")
            return False
    
    async def _fetch_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """
        Fetch tenant configuration from Supabase
        
        Args:
            tenant_id: The tenant identifier
            
        Returns:
            Dict containing tenant configuration or empty dict if not found
        """
        try:
            supabase = get_supabase_client()
            response = await asyncio.to_thread(
                lambda: supabase.table("tenant_configs")
                .select("*")
                .eq("tenant_id", tenant_id)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                self.logger.info(f"Found tenant config for tenant_id: {tenant_id}")
                return response.data[0]
            else:
                self.logger.warning(f"No tenant config found for tenant_id: {tenant_id}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error fetching tenant config: {str(e)}")
            return {}

    async def _fetch_call_details(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch call details from Supabase
        
        Args:
            call_sid: The Exotel call SID
            
        Returns:
            Dict containing call details or None if not found
        """
        try:
            # Initialize merged_details to store combined data
            merged_details = {}
            found_any_data = False
            
            # First check exotel_call_details for phone number and basic info
            self.logger.info(f"Checking exotel_call_details for {call_sid}")
            exotel_details_response = self.supabase.table("exotel_call_details").select("*").eq("call_sid", call_sid).execute()
            
            if exotel_details_response and hasattr(exotel_details_response, 'data') and len(exotel_details_response.data) > 0:
                self.logger.info(f"Found call details in exotel_call_details table for {call_sid}")
                exotel_data = exotel_details_response.data[0]
                merged_details.update(exotel_data)  # Add all exotel data to merged details
                found_any_data = True
                self.logger.info(f"Phone number from exotel_call_details: {merged_details.get('from_number')}")
            
            # Then check call_details for transcript and analysis data
            self.logger.info(f"Checking call_details for {call_sid}")
            call_details_response = self.supabase.table("call_details").select("*").eq("call_sid", call_sid).execute()
            
            if call_details_response and hasattr(call_details_response, 'data') and len(call_details_response.data) > 0:
                self.logger.info(f"Found call details in call_details table for {call_sid}")
                call_data = call_details_response.data[0]
                # Update merged details with call_details data, but don't overwrite from_number if it exists
                for key, value in call_data.items():
                    if key != 'from_number' or 'from_number' not in merged_details:
                        merged_details[key] = value
                found_any_data = True
            
            if found_any_data:
                self.logger.info(f"Merged call details keys: {list(merged_details.keys())}")
                self.logger.info(f"Final from_number: {merged_details.get('from_number')}")
                return merged_details
            
            self.logger.warning(f"No call details found in any table for {call_sid}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching call details: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
        
    def _format_phone_number(self, phone: Optional[str]) -> Optional[str]:
        """
        Format phone number for MSG91 (should start with country code)
        
        Args:
            phone: Raw phone number from database
            
        Returns:
            Formatted phone number or None if invalid
        """
        if not phone:
            self.logger.warning("Empty phone number provided to formatter")
            return None
            
        self.logger.info(f"Formatting phone number: '{phone}'")
            
        # Strip any non-digit characters
        digits_only = ''.join(filter(str.isdigit, str(phone)))
        self.logger.info(f"After stripping non-digits: '{digits_only}'")
        
        # Handle different formats
        if len(digits_only) == 10:
            # 10-digit number, add 91 prefix (no + for MSG91)
            formatted = f"91{digits_only}"
            self.logger.info(f"Formatted 10-digit number: '{formatted}'")
            return formatted
        elif len(digits_only) > 10:
            # Check if it already has country code
            if digits_only.startswith('91') and len(digits_only) >= 12:
                # Already has 91 prefix
                self.logger.info(f"Number already has 91 prefix: '{digits_only}'")
                return digits_only
            elif digits_only.startswith('0'):
                # Remove leading 0 and add 91
                formatted = f"91{digits_only[1:]}"
                self.logger.info(f"Removed leading 0 and added 91: '{formatted}'")
                return formatted
            else:
                # Add 91 prefix if not present
                formatted = f"91{digits_only}"
                self.logger.info(f"Added 91 prefix to number: '{formatted}'")
                return formatted
        
        self.logger.warning(f"Invalid phone number format: '{phone}' (digits: '{digits_only}')")
        return None
        
    @async_retry(max_retries=3, delay=2, backoff=2, exceptions=(Exception,))
    async def _send_customer_notification(self, phone: str, data: Dict[str, Any], tenant_id: str, call_sid: str) -> bool:
        """
        Send notification to customer with retry mechanism
        
        Args:
            phone: Customer's phone number
            data: Message data (call_type, details)
            tenant_id: The tenant identifier
            call_sid: The Exotel call SID
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        self.logger.info(f"Sending customer notification to {phone}")
        
        # Ensure phone is properly formatted for MSG91
        formatted_phone = phone
        if not phone:
            self.logger.error("No phone number provided for customer notification")
            return False
            
        # If phone doesn't start with 91, try to format it
        if not str(phone).startswith("91"):
            self.logger.warning(f"Phone number {phone} doesn't start with '91', attempting to format")
            formatted_phone = self._format_phone_number(phone)
            if not formatted_phone:
                self.logger.error(f"Failed to format phone number: {phone}")
                return False
            self.logger.info(f"Reformatted phone number from {phone} to {formatted_phone}")
        
        # Get call type from data
        call_type = data.get("call_type")
        if not call_type:
            self.logger.error("No call_type provided for customer notification")
            return False
            
        # Use service_message template directly for all customer notifications
        template_name = "service_message.json"
        self.logger.info(f"Using service_message template for customer {call_type} notification")
            
        # Generate AI message for the customer
        ai_message = await self.whatsapp_service.generate_ai_message(
            call_type=call_type,
            critical_call_details=data
        )
        
        if not ai_message:
            self.logger.error(f"Failed to generate AI message for call_sid: {call_sid}")
            return False
            
        # Log the AI-generated message
        # ai_message is a dictionary, so we need to convert it to string first before slicing
        ai_message_str = str(ai_message) if isinstance(ai_message, dict) else ai_message
        self.logger.info(f"AI generated message for customer: {ai_message_str[:50]}...")
        
        # Prepare template data for MSG91 provider (matching test script format)
        template_data = {
            "phone_numbers": [formatted_phone],  # Must be a list, not a string
            "branch_name": "Test Branch",  # Default branch name
            "message_body": ai_message,  # This should be the dictionary with body_1, body_2, etc.
            "branch_head_phone": self.owner_phone  # Use configured owner phone
        }
        
        self.logger.info(f"Template data prepared for customer notification: {template_data}")
        
        if not template_data:
            self.logger.error(f"Failed to prepare template data for call_sid: {call_sid}")
            return False
            
        try:
            # Send using MSG91 provider directly (skip render_template to avoid issues)
            result = await self.msg91_provider.send_message(
                to_number=formatted_phone,
                template_name="service_message",  # Use service_message template directly
                template_data=template_data  # Pass template_data directly
            )
            self.logger.info(f"Customer notification result: {result}")
            return result.get('status') == 'success' if isinstance(result, dict) else bool(result)
        except Exception as e:
            self.logger.error(f"Error sending customer notification: {str(e)}")
            raise  # Re-raise for retry mechanism
        
    @async_retry(max_retries=3, delay=2, backoff=2, exceptions=(Exception,))
    async def _send_owner_notification(self, phone: str, data: Dict[str, Any], 
                                        customer_phone: str, tenant_id: str,
                                        return_exceptions: bool = False) -> bool:
        """
        Send notification to business owner with retry mechanism
        
        Args:
            phone: Owner's phone number
            data: Message data (call_type, details)
            customer_phone: Customer's phone number
            tenant_id: The tenant identifier
            return_exceptions: Whether to return exceptions instead of raising them
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        self.logger.info(f"Sending owner notification to {phone} about customer {customer_phone}")
        
        # Ensure owner phone is properly formatted for MSG91
        formatted_phone = phone
        if not phone:
            self.logger.error("No phone number provided for owner notification")
            return False
            
        # If phone doesn't start with 91, try to format it
        if not str(phone).startswith("91"):
            self.logger.warning(f"Owner phone number {phone} doesn't start with '91', attempting to format")
            formatted_phone = self._format_phone_number(phone)
            if not formatted_phone:
                self.logger.error(f"Failed to format owner phone number: {phone}")
                return False
            self.logger.info(f"Reformatted owner phone number from {phone} to {formatted_phone}")
            
        # Format customer phone for template if needed
        formatted_customer_phone = customer_phone
        if customer_phone and not str(customer_phone).startswith("91"):
            formatted_customer_phone = self._format_phone_number(customer_phone) or customer_phone
        
        # Get call type and critical call details
        call_type = data.get("call_type", "Unknown")
        critical_call_details = data.get("critical_call_details", {})
        
        # Extract summary from critical call details
        summary = ""
        if isinstance(critical_call_details, dict) and "summary" in critical_call_details:
            summary = critical_call_details.get("summary", "")
        
        # Format critical call details as pipe-separated key-value pairs
        formatted_details = self._format_critical_details_for_owner(critical_call_details)
        
        # Prepare template data for owner_message template
        # var1: Customer phone number
        # var2: Call type
        # var3: Summary
        # var4: Pipe-separated key-value pairs from critical_call_details
        template_data = {
            "phone_numbers": formatted_phone,
            "var1": formatted_customer_phone,
            "var2": call_type,
            "var3": summary,
            "var4": formatted_details
        }
        
        self.logger.info(f"Template data prepared for owner notification using owner_message template")
        
        try:
            result = await self.msg91_provider.send_message(
                to_number=formatted_phone,
                template_name="owner_message",
                template_data=template_data
            )
            self.logger.info(f"Owner notification result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error sending owner notification: {str(e)}")
            if return_exceptions:
                return e
            raise  # Re-raise for retry mechanism
        
    def _prepare_owner_message(self, call_details: Dict[str, Any], customer_phone: str, tenant_id: str) -> str:
        """
        Prepare a simple message for owner notification
        
        Args:
            call_details: Call details from the database
            customer_phone: Customer phone number
            tenant_id: Tenant ID
            
        Returns:
            String with the message for the owner
        """
        # Create a simple message with the call details
        call_type = call_details.get('call_type', 'Unknown')
        call_duration = call_details.get('call_duration', 'Unknown')
        
        # Extract any critical details if available
        critical_details = ""
        if 'critical_call_details' in call_details and call_details['critical_call_details']:
            critical_details = "\n\nDetails: " + call_details['critical_call_details']
        
        # Format the message
        message = f"📞 New {call_type} call received from {customer_phone}\n"
        message += f"⏱️ Duration: {call_duration} seconds{critical_details}"
        
        return message
        
    def _format_critical_details_for_owner(self, critical_call_details: Dict[str, Any]) -> str:
        """
        Format critical call details as pipe-separated key-value pairs for owner notification
        
        Args:
            critical_call_details: Critical call details from the analyzer
            
        Returns:
            String with pipe-separated key-value pairs
        """
        if not critical_call_details or not isinstance(critical_call_details, dict):
            return "No details available"
            
        # Filter out summary as it's already included in var3
        filtered_details = {k: v for k, v in critical_call_details.items() if k != "summary"}
        
        if not filtered_details:
            return "No additional details available"
            
        # Format as pipe-separated key-value pairs
        formatted_pairs = []
        for key, value in filtered_details.items():
            # Format key with title case and replace underscores with spaces
            formatted_key = key.replace("_", " ").title()
            
            # Handle different value types
            if isinstance(value, (list, tuple)):
                formatted_value = ", ".join(str(item) for item in value)
            elif isinstance(value, dict):
                nested_pairs = [f"{k}: {v}" for k, v in value.items()]
                formatted_value = ", ".join(nested_pairs)
            else:
                formatted_value = str(value)
                
            formatted_pairs.append(f"{formatted_key}: {formatted_value}")
            
        return " | ".join(formatted_pairs)
        
    def _prepare_customer_template_data(self, data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Prepare template data for customer message
        
        Args:
            data: Message data (call_type, details)
            tenant_id: The tenant identifier
            
        Returns:
            Dict with template components
        """
        # Use the same format as owner template for consistency
        # This matches the service_message template structure
        # The message_body is the AI-generated message from WhatsAppNotificationService.generate_ai_message
        # It's passed through template_data['message_body'] from the render_template method
        return {
            "body": {
                "type": "text",
                "text": data.get("message_body", f"Thank you for your call! We've noted your {data['call_type']}. Our team will be in touch with you soon.")
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
            # Note: execute() is synchronous and returns APIResponse, not awaitable
            self.supabase.table("notifications").insert({
                "call_sid": call_sid,
                "notification_type": "whatsapp",
                "recipient": "multiple",  # Required field - cannot be null
                "recipient_type": "mixed",  # Required field - cannot be null
                "status": "success" if success_count == total_count else "partial_failure",
                "payload": json.dumps({  # Use payload instead of details to match schema
                    "success_count": success_count,
                    "total_count": total_count,
                    "timestamp": str(asyncio.get_event_loop().time())
                })
            }).execute()
            
        except Exception as e:
            self.logger.error(f"Error logging notification results: {str(e)}")
