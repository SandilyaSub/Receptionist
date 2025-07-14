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
        
        # Template mapping based on call_type - using service_booking for all types
        self.template_mapping = {
            "Booking": "service_message.json",
            "Informational": "service_message.json",
            # Default to service_message for any other call types
            "Unknown": "service_message.json"
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
        system_instruction = """
You are an exceptional copywriter, expertly crafting WhatsApp messages for a receptionist system that excels at customer communication.

Your core responsibility is to transform raw call details into polished, customer-facing WhatsApp messages. The receptionist will provide you with the call_type (e.g., booking, cancellation, enquiry) and critical_call_details pertinent to the customer's interaction.

Your goal is to generate a complete WhatsApp message body that will be sent directly to customers. Format the message as a single line with pipe separators (|) between different sections for maximum readability and engagement.

FORMATTING REQUIREMENTS:
- Use pipe separators (|) between different sections instead of line breaks
- Use *bold text* for emphasis on key information
- Use _italic text_ for field labels/descriptions
- Include relevant emojis to enhance readability
- Keep the message concise but include ALL provided critical_call_details
- End with a brief, inoffensive, universally appropriate pun

STRUCTURE FORMAT:
🎉 *[Opening confirmation message with customer name if available]* | _[Field1]:_ *[Value1]* | _[Field2]:_ *[Value2]* | _[Field3]:_ *[Value3]* | [Additional relevant information] | Thank you for choosing *[Business Name]*! [relevant emoji] | [Brief pun related to the business]

EXAMPLE OUTPUT:
🎉 *Your cake booking is confirmed, Sandy K!* | _Date:_ *July 15, 2025* | _Time:_ *3:00 PM* | _Type:_ *Birthday Cake* | _Flavor:_ *Chocolate* | We'll call you 24 hours before delivery to confirm | Thank you for choosing *Lovable Bakery*! 🍰 | That's what I call a sweet deal! 🎂

IMPORTANT NOTES:
- Always use pipe separators (|) between sections
- Include customer name in the opening if provided
- Use appropriate emojis for the business type (🍰 for bakery, 🎂 for cakes, etc.)
- Keep each section concise but informative
- All critical details must be included in a customer-friendly format
"""
        
        try:
            # Use the genai package exactly as in transcript_analyzer.py
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Log the input data for debugging
            self.logger.info(f"Input data for AI message generation: {json.dumps(input_data, indent=2)}")
            
            # Format call details in a more structured way
            details_str = ""
            if input_data.get('critical_call_details'):
                for key, value in input_data['critical_call_details'].items():
                    details_str += f"{key}: {value}\n"
            
            # Create a more structured prompt with clear instructions for formatting and style
            prompt = f"""
            Create a WhatsApp notification message for a {input_data.get('call_type', 'Unknown')} call with the following details:
            
            {details_str}
            """
            
            # Create system instruction for better message quality
            system_instruction = """
            You are an exceptional copywriter, expertly crafting WhatsApp messages for a receptionist system that excels at customer communication.
            
            Your core responsibility is to transform raw call details into polished, customer-facing WhatsApp messages. 
            
            Format the message with this specific structure:
            1. Start with an emoji and a friendly greeting/confirmation message
            2. Add a "Details:" section with bullet points
            3. Each detail should have a relevant emoji prefix
            4. End with a brief, appropriate pun related to the business
            
            IMPORTANT: For all line breaks in your message, use HTML <br> tags instead of regular newlines.
            For example, instead of writing:
            🎉 Your booking is confirmed!
            Details:
            
            Write:
            🎉 Your booking is confirmed!<br>Details:<br>
            
            Example format with proper <br> tags:
            🎉 Your [PRODUCT] booking is confirmed! 🎂<br>Details:<br>🗓️ Pickup: [DATE]<br>⏰ Time: [TIME]<br>⚖️ Weight: [WEIGHT]<br>🍰 Shape: [SHAPE]<br>[FUN CLOSING LINE WITH PUN]
            
            Use emojis generously but appropriately to enhance readability and engagement.
            Keep the message concise, friendly, and visually organized.
            Include ALL the provided details in a customer-friendly format.
            Remember to use <br> tags for ALL line breaks to ensure proper formatting in WhatsApp.
            """
            
            self.logger.info(f"Sending prompt to Gemini API:\n{prompt}")
            
            # Call the model using asyncio.to_thread to avoid blocking - simplified API call
            try:
                # Create contents using the types.Content and types.Part format from the cookbook
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt),
                        ],
                    ),
                ]
                
                # Create generate_content_config using the exact format from the cookbook
                generate_content_config = types.GenerateContentConfig(
                    temperature=0.7,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=0,
                    ),
                    safety_settings=[
                        types.SafetySetting(
                            category="HARM_CATEGORY_HARASSMENT",
                            threshold="BLOCK_NONE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_HATE_SPEECH",
                            threshold="BLOCK_NONE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            threshold="BLOCK_NONE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_DANGEROUS_CONTENT",
                            threshold="BLOCK_NONE",
                        ),
                    ],
                    response_mime_type="text/plain",
                    system_instruction=[
                        types.Part.from_text(text=system_instruction),
                    ],
                )
                
                # Call the model with the config parameter exactly as in the cookbook
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=generate_content_config,
                )
                
                # Log the raw response for debugging
                self.logger.info(f"Raw Gemini API response: {response}")
                
                if not response or not hasattr(response, 'text'):
                    self.logger.error("Invalid response from Gemini API: missing 'text' attribute")
                    raise ValueError("Invalid response from Gemini API: missing 'text' attribute")
                    
                self.logger.info(f"AI generated message: {response.text}")
                return response.text.strip()
                
            except Exception as api_error:
                self.logger.error(f"Error in Gemini API call: {str(api_error)}")
                raise  # Re-raise to be caught by the outer exception handler
                
        except Exception as e:
            self.logger.error(f"Error generating AI message: {str(e)}")
            self.logger.exception("Full exception details:")
            # Fallback message in case of error
            return "Thank you for your call. We'll be in touch soon."
    
    def format_phone_number(self, phone: str) -> str:
        """
        Format phone number from Exotel format to MSG91 format
        
        Args:
            phone: Phone number in Exotel format (e.g., '09901678665')
            
        Returns:
            Phone number in MSG91 format (e.g., '919901678665')
        """
        # Remove any leading zeros
        phone = phone.lstrip('0')
        
        # Add country code if not present
        if not phone.startswith('91'):
            phone = '91' + phone
            
        return phone
    
    async def gather_template_data(self, call_sid: str, tenant_id: str, call_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gather all data needed for the template
        
        Args:
            call_sid: The Exotel call SID
            tenant_id: The tenant ID
            call_details: Call details from the analyzer
            
        Returns:
            Dict with data for the template or empty dict if data gathering failed
        """
        try:
            # Fetch customer phone number from Exotel call details
            supabase = get_supabase_client()
            exotel_response = await asyncio.to_thread(
                lambda: supabase.table("exotel_call_details")
                .select("*")
                .eq("call_sid", call_sid)
                .execute()
            )
            
            if not exotel_response or not exotel_response.data or len(exotel_response.data) == 0:
                self.logger.error(f"No Exotel call details found for call_sid: {call_sid}")
                return {}
                
            exotel_data = exotel_response.data[0]
            customer_phone = exotel_data.get("from_number")
            
            if not customer_phone:
                self.logger.error(f"No customer phone number found for call_sid: {call_sid}")
                return {}
                
            # Format the phone number to MSG91 format
            customer_phone = self.format_phone_number(customer_phone)
            
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
            
            # Get call type and critical call details
            call_type = call_details.get("call_type")
            critical_call_details = call_details.get("critical_call_details", {})
            
            if not call_type:
                self.logger.error(f"No call_type found in call_details for call_sid: {call_sid}")
                return {}
                
            message_body = await self.generate_ai_message(call_type, critical_call_details)
            
            # Format the template data according to MSG91 WhatsApp template requirements
            # body_1.value = branch_name from tenant_configs
            # body_2.value = AI-generated message body
            # body_3.value = branch_head_phone_number from tenant_configs
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
        Simplified template rendering that just passes through the message body
        
        Args:
            template_name: Name of the template file (not used in simplified version)
            template_data: Data to insert into the template
            
        Returns:
            Dict with the template data containing message_body
        """
        try:
            # No need to parse template files anymore, just pass through the data
            # The MSG91Provider will handle the proper formatting
            
            # Ensure message_body is never null
            message_body = template_data.get("message_body", "")
            if message_body is None or message_body == "":
                message_body = "Thank you for your call. We'll be in touch soon."
                
            # Log the message being sent
            self.logger.info(f"Rendering template with message: {message_body[:50]}...")
            
            # Just return the template data as is - MSG91Provider will extract what it needs
            return template_data
            
        except Exception as e:
            self.logger.error(f"Error rendering template: {str(e)}")
            return None
