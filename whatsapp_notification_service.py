"""
WhatsApp Notification Service for Receptionist AI

This module handles WhatsApp notifications with AI-generated message content
using Gemini Flash 2.5 model and MSG91 templates.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from google import genai
from google.genai import types
from supabase_client import get_supabase_client

# Configure Gemini API - not needed, we'll use the Client approach as in transcript_analyzer.py
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class WhatsAppNotificationService:
    """Service for sending WhatsApp notifications with AI-generated content"""
    
    def __init__(self, logger=None):
        """
        Initialize the WhatsApp notification service
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self.templates_dir = Path(__file__).parent / "msgTemplates"
        
        # Template mapping based on call_type
        self.template_mapping = {
            "Booking": "booking_details.json",
            "Informational": "information.json"
        }
        
        # Validate initialization
        if not GEMINI_API_KEY:
            self.logger.warning("WhatsApp notification service initialized without GEMINI_API_KEY")
        
        if not self.templates_dir.exists():
            self.logger.warning(f"Templates directory not found: {self.templates_dir}")
    
    async def select_template(self, call_type: str) -> Optional[str]:
        """
        Select the appropriate template based on call_type
        
        Args:
            call_type: Type of call (e.g., "Booking", "Informational")
            
        Returns:
            Template filename or None if no template is configured for this call_type
        """
        template_name = self.template_mapping.get(call_type)
        
        if not template_name:
            self.logger.info(f"No WhatsApp template configured for call_type: {call_type}")
            return None
            
        template_path = self.templates_dir / template_name
        if not template_path.exists():
            self.logger.error(f"Template file not found: {template_path}")
            return None
            
        return template_name
    
    async def fetch_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
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
                return response.data[0]
            else:
                self.logger.warning(f"No tenant config found for tenant_id: {tenant_id}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error fetching tenant config: {str(e)}")
            return {}
    
    async def generate_ai_message(self, call_type: str, critical_call_details: Dict[str, Any]) -> str:
        """
        Generate WhatsApp message using Gemini Flash 2.5
        
        Args:
            call_type: Type of call (e.g., "Booking", "Informational")
            critical_call_details: Details extracted from the call
            
        Returns:
            AI-generated message text or error message
        """
        if not GEMINI_API_KEY:
            self.logger.error("Cannot generate message: GEMINI_API_KEY not configured")
            return "Unable to generate message: API key not configured"
        input_data = {
            "call_type": call_type,
            "critical_call_details": critical_call_details
        }
        
        # System instructions for the AI
        system_instructions = """
        You are an exceptional copywriter, expertly crafting WhatsApp messages for a receptionist system that excels at customer communication.

        Your core responsibility is to transform raw call details into polished, customer-facing WhatsApp messages. The receptionist will provide you with the call_type (e.g., booking, cancellation, enquiry) and critical_call_details pertinent to the customer's interaction.

        Your goal is to generate the complete body of a WhatsApp message. This message will be directly copied into a cURL command from one of our service providers, requiring it to be in a rich WhatsApp text format. Utilize bolding, italics, and relevant emojis to ensure maximum readability and engagement. The message must clearly and concisely incorporate all provided critical_call_details. Finally, conclude the message with a very brief, inoffensive, humorous, and universally appropriate pun.
        """
        
        try:
            # Use the genai package exactly as in transcript_analyzer.py
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Convert input data to a prompt string
            prompt = json.dumps(input_data)
            
            # Call the model using asyncio.to_thread to avoid blocking - exactly as in transcript_analyzer.py
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="text/plain",
                    system_instruction=system_instructions,
                    temperature=0.7,
                    max_output_tokens=500
                )
            )
            
            self.logger.debug(f"AI response text: {response.text}")
            return response.text
                
        except Exception as e:
            self.logger.error(f"Error generating AI message: {str(e)}")
            # Fallback message in case of error
            return "Thank you for your call. We'll be in touch soon."
    
    async def gather_template_data(self, call_sid: str, tenant_id: str, call_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gather all data needed for the template
        
        Args:
            call_sid: The Exotel call SID
            tenant_id: The tenant identifier
            call_details: Call details including call_type and critical_call_details
            
        Returns:
            Dict with all template variables or empty dict if required data is missing
        """
        try:
            # Get from_number from exotel_call_details
            supabase = get_supabase_client()
            exotel_response = await asyncio.to_thread(
                lambda: supabase.table("exotel_call_details")
                .select("*")
                .eq("call_sid", call_sid)
                .execute()
            )
            
            if not exotel_response.data or len(exotel_response.data) == 0:
                self.logger.error(f"No exotel_call_details found for call_sid: {call_sid}")
                return {}
                
            exotel_data = exotel_response.data[0]
            customer_phone = exotel_data.get("from_number")
            
            if not customer_phone:
                self.logger.error(f"No customer phone number found for call_sid: {call_sid}")
                return {}
            
            # Get tenant config data
            tenant_data = await self.fetch_tenant_config(tenant_id)
            if not tenant_data:
                self.logger.error(f"No tenant config data found for tenant_id: {tenant_id}")
                return {}
                
            branch_name = tenant_data.get("branch_name")
            branch_head_phone = tenant_data.get("branch_head_phone_number")
            
            if not branch_name or not branch_head_phone:
                self.logger.error(f"Missing branch_name or branch_head_phone_number for tenant_id: {tenant_id}")
                return {}
            
            # Generate AI message
            call_type = call_details.get("call_type")
            critical_call_details = call_details.get("critical_call_details", {})
            
            if not call_type:
                self.logger.error(f"No call_type found in call_details for call_sid: {call_sid}")
                return {}
                
            message_body = await self.generate_ai_message(call_type, critical_call_details)
            
            return {
                "phone_numbers": [customer_phone],
                "branch_name": branch_name,
                "message_body": message_body,
                "branch_head_phone": branch_head_phone
            }
            
        except Exception as e:
            self.logger.error(f"Error gathering template data: {str(e)}")
            return {}
    
    async def render_template(self, template_name: str, template_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Render the template with the provided data
        
        Args:
            template_name: Name of the template file
            template_data: Data to insert into the template
            
        Returns:
            Dict with the rendered template or None if rendering failed
        """
        try:
            template_path = self.templates_dir / template_name
            with open(template_path, "r") as f:
                template_content = f.read()
                
            # Extract the JSON part from the curl command
            json_start = template_content.find('{')
            json_end = template_content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                self.logger.error(f"Invalid template format in {template_name}")
                return None
                
            template_json = json.loads(template_content[json_start:json_end])
            
            # Insert variables
            template_json["to"] = template_data["phone_numbers"]
            
            # Access the components section
            components = template_json["payload"]["template"]["to_and_components"][0]["components"]
            
            # Update component values
            components["body_1"]["value"] = template_data["branch_name"]
            components["body_2"]["value"] = template_data["message_body"]
            components["body_3"]["value"] = template_data["branch_head_phone"]
            
            return template_json
            
        except Exception as e:
            self.logger.error(f"Error rendering template: {str(e)}")
            return None
