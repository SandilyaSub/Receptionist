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
            
        # Define the system instructions for the AI as a class attribute
        self.ai_system_instruction = """
You are an exceptional copywriter creating WhatsApp messages for a receptionist AI system. Your role is to transform call details into engaging, customer-friendly WhatsApp message components.

You will receive call_type and critical_call_details from customer interactions. Your task is to generate content for a 4-component WhatsApp template structure that creates delightful, personality-rich messages.

COMPONENT STRUCTURE:
The message follows this format:
"Hi {{body_1}}! 👋

{{body_2}}

{{body_3}}

{{body_4}}

Thanks for choosing us! 🙏

Regards,
Aarohi ( helllo.ai )"

YOUR TASK:
Generate a JSON response with exactly 4 components:

{
  "body_1": "Customer name or appropriate greeting",
  "body_2": "Context acknowledgment with appropriate emoji",
  "body_3": "Key details/confirmation/next steps",
  "body_4": "Closing message with personality and relevant emoji"
}

COMPONENT GUIDELINES:

body_1: 
- Use customer name if available in critical_call_details
- If no name, use "there" or appropriate greeting
- Just the name/greeting, no additional text

body_2:
- Acknowledge the call context with enthusiasm
- Include 1-2 relevant emojis
- Keep it conversational and warm
- Examples: "Just confirmed your cake order - 2 delicious treats coming your way! 🎂", "Thanks for your interest in our digital wedding invitations! 💌"

body_3:
- Include ALL critical details from the call
- Format key information clearly
- Use specific details like dates, times, prices, quantities
- Be comprehensive but concise
- Examples: "1kg Dutch Truffle (round) + 0.5kg Butterscotch (square), both eggless. Ready tomorrow at 6 PM!", "2D invitations: ₹1,500-₹2,900 | 3D with caricatures: ₹3,500-₹4,500. 1-day delivery!"

body_4:
- Personality-driven closing message
- Include relevant emoji
- Match the business context
- Create anticipation or warmth
- Examples: "We'll have your birthday surprises ready! See you tomorrow! ✨", "Ready to make your special day unforgettable? 🎉"

IMPORTANT RULES:
- Always return valid JSON with exactly these 4 keys
- No newlines within component values
- Include relevant emojis but don't overuse them
- Match tone to business type (playful for bakery, elegant for invitations, professional for medical)
- ALL critical details must be included in body_3
- Keep messages warm, engaging, and professional

BUSINESS CONTEXT ADAPTATION:
- Bakery: Use food emojis (🎂🍰🧁), warm language about treats and celebrations
- Joy Invite: Use celebration emojis (💕🎉💌), romantic/festive language
- Medical: Use professional emojis (🏥🩺), caring but professional tone
- General: Adapt emoji and tone to context

EXAMPLE OUTPUT:
{
  "body_1": "Sandy",
  "body_2": "Just confirmed your cake order - 2 delicious treats coming your way! 🎂",
  "body_3": "1kg Dutch Truffle (round) + 0.5kg Butterscotch (square), both eggless as requested. Ready for pickup tomorrow at 6 PM sharp!",
  "body_4": "We'll have your birthday surprises wrapped and ready! See you tomorrow! ✨"
}
"""
    
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
    
    async def generate_ai_message(self, call_type: str, critical_call_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate WhatsApp message using Gemini Flash 2.5
        
        Args:
            call_type: Type of call (e.g., "Booking", "Informational")
            critical_call_details: Details extracted from the call
            
        Returns:
            AI-generated message components as a dictionary or error message
        """
        if not GEMINI_API_KEY:
            self.logger.error("Cannot generate message: GEMINI_API_KEY not configured")
            return "Unable to generate message: API key not configured"
        input_data = {
            "call_type": call_type,
            "critical_call_details": critical_call_details
        }
        
        # Use the class attribute for system instruction defined in __init__
        self.logger.info("Using 4-component JSON format for customer notification")        
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
            
            # Create a structured prompt that explicitly asks for the 4-component JSON format
            prompt = f"""
            Create a WhatsApp notification message for a {input_data.get('call_type', 'Unknown')} call with the following details:
            
            {details_str}
            
            Remember to return your response as a valid JSON object with exactly four components (body_1, body_2, body_3, body_4) as specified in the system instructions.
            """
            
            # Use the class attribute for system instruction
            self.logger.info("Using 4-component JSON format for customer notification")
            
            
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
                        types.Part.from_text(text=self.ai_system_instruction),
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
                
                # Try to parse the response as JSON
                try:
                    message_components = json.loads(response.text.strip())
                    
                    # Validate that all required components are present
                    required_components = ["body_1", "body_2", "body_3", "body_4"]
                    missing_components = [comp for comp in required_components if comp not in message_components]
                    
                    if missing_components:
                        self.logger.warning(f"Missing components in AI response: {missing_components}")
                        # Add default values for missing components
                        for comp in missing_components:
                            if comp == "body_1":
                                message_components[comp] = "there"
                            elif comp == "body_2":
                                message_components[comp] = "Thank you for your inquiry."
                            elif comp == "body_3":
                                message_components[comp] = "We've received your message and will follow up shortly."
                            elif comp == "body_4":
                                message_components[comp] = "We look forward to serving you soon!"
                    
                    self.logger.info(f"Generated message components: {json.dumps(message_components, indent=2)}")
                    return message_components
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse AI response as JSON: {str(e)}")
                    self.logger.error(f"Raw response: {response.text}")
                    # Return default message components
                    return {
                        "body_1": "there",
                        "body_2": "Thank you for your inquiry.",
                        "body_3": "We've received your message and will follow up shortly.",
                        "body_4": "We look forward to serving you soon!"
                    }
                
            except Exception as api_error:
                self.logger.error(f"Error in Gemini API call: {str(api_error)}")
                raise  # Re-raise to be caught by the outer exception handler
                
        except Exception as e:
            self.logger.error(f"Error generating AI message: {str(e)}")
            self.logger.exception("Full exception details:")
            # Fallback message in case of error
            return {
                "body_1": "there",
                "body_2": "Thank you for your inquiry.",
                "body_3": "We've received your message and will follow up shortly.",
                "body_4": "We look forward to serving you soon!"
            }
    
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
            # The message_body now contains a dictionary with body_1, body_2, body_3, body_4 components
            return {
                "phone_numbers": [customer_phone],
                "branch_name": branch_name,
                "message_body": message_body,  # This is now a dictionary with the 4 components
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
