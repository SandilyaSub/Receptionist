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

# Configure Gemini API
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
        
        # Updated template mapping - using universal template for all call types
        self.template_mapping = {
            "Booking": "service_message.json",
            "Informational": "service_message.json",
            "Cancellation": "service_message.json",
            "Pricing Enquiry": "service_message.json",
            "Status Check": "service_message.json",
            "Initial Enquiry": "service_message.json"
        }
        
        # Validate initialization
        if not GEMINI_API_KEY:
            self.logger.warning("WhatsApp notification service initialized without GEMINI_API_KEY")
        
        if not self.templates_dir.exists():
            self.logger.warning(f"Templates directory not found: {self.templates_dir}")
            
        # Updated system instructions for 4-component template
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
        template_name = self.template_mapping.get(call_type, "service_message.json")
        
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
    
    async def generate_ai_message_components(self, call_type: str, critical_call_details: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate WhatsApp message components using Gemini Flash 2.5
        
        Args:
            call_type: Type of call (e.g., "Booking", "Informational")
            critical_call_details: Details extracted from the call
            
        Returns:
            Dict with body_1, body_2, body_3, body_4 components or fallback components
        """
        if not GEMINI_API_KEY:
            self.logger.error("Cannot generate message: GEMINI_API_KEY not configured")
            return self._get_fallback_components()
            
        input_data = {
            "call_type": call_type,
            "critical_call_details": critical_call_details
        }
        
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Log the input data for debugging
            self.logger.info(f"Input data for AI message generation: {json.dumps(input_data, indent=2)}")
            
            # Format call details in a structured way
            details_str = ""
            if input_data.get('critical_call_details'):
                for key, value in input_data['critical_call_details'].items():
                    details_str += f"{key}: {value}\n"
            
            # Create a structured prompt for component generation
            prompt = f"""
            Generate WhatsApp message components for a {input_data.get('call_type', 'Unknown')} call with the following details:
            
            {details_str}
            
            Please provide a JSON response with exactly 4 components: body_1, body_2, body_3, and body_4.
            """
            
            self.logger.info(f"Sending prompt to Gemini API:\n{prompt}")
            
            try:
                # Create contents using the types.Content and types.Part format
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt),
                        ],
                    ),
                ]
                
                # Create generate_content_config
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
                    response_mime_type="application/json",  # Changed to JSON
                    system_instruction=[
                        types.Part.from_text(text=self.ai_system_instruction),
                    ],
                )
                
                # Call the model
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
                    return self._get_fallback_components()
                
                # Parse JSON response
                try:
                    components = json.loads(response.text.strip())
                    
                    # Validate that all required components are present
                    required_keys = ['body_1', 'body_2', 'body_3', 'body_4']
                    if not all(key in components for key in required_keys):
                        self.logger.error(f"Missing required components in AI response: {components}")
                        return self._get_fallback_components()
                    
                    # Ensure no component is empty
                    for key in required_keys:
                        if not components[key] or components[key].strip() == "":
                            components[key] = "Thank you for your call"
                    
                    self.logger.info(f"AI generated components: {components}")
                    return components
                    
                except json.JSONDecodeError as json_error:
                    self.logger.error(f"Failed to parse JSON response: {json_error}")
                    self.logger.error(f"Raw response text: {response.text}")
                    return self._get_fallback_components()
                    
            except Exception as api_error:
                self.logger.error(f"Error in Gemini API call: {str(api_error)}")
                return self._get_fallback_components()
                
        except Exception as e:
            self.logger.error(f"Error generating AI message components: {str(e)}")
            self.logger.exception("Full exception details:")
            return self._get_fallback_components()
    
    def _get_fallback_components(self) -> Dict[str, str]:
        """
        Get fallback components in case of AI generation failure
        
        Returns:
            Dict with fallback components
        """
        return {
            "body_1": "there",
            "body_2": "Thank you for your call! We received your request. 📞",
            "body_3": "Our team will review your requirements and get back to you soon with all the details.",
            "body_4": "We appreciate your patience and look forward to serving you! 🙏"
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
                
            # Generate AI message components
            message_components = await self.generate_ai_message_components(call_type, critical_call_details)
            
            # Format the template data with 4 components
            return {
                "phone_numbers": [customer_phone],
                "branch_name": branch_name,
                "branch_head_phone": branch_head_phone,
                "components": message_components
            }
            
        except Exception as e:
            self.logger.error(f"Error gathering template data: {str(e)}")
            return {}
    
    async def render_template(self, template_name: str, template_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Render template with the 4-component structure
        
        Args:
            template_name: Name of the template file
            template_data: Data to insert into the template
            
        Returns:
            Dict with the rendered template data
        """
        try:
            components = template_data.get("components", {})
            
            # Ensure all components exist with fallbacks
            rendered_components = {
                "body_1": components.get("body_1", "there"),
                "body_2": components.get("body_2", "Thank you for your call! 📞"),
                "body_3": components.get("body_3", "We'll be in touch soon with all the details."),
                "body_4": components.get("body_4", "We appreciate your patience! 🙏")
            }
            
            # Log the components being sent
            self.logger.info(f"Rendering template with components: {rendered_components}")
            
            # Return the template data with rendered components
            return {
                "phone_numbers": template_data.get("phone_numbers", []),
                "branch_name": template_data.get("branch_name", ""),
                "branch_head_phone": template_data.get("branch_head_phone", ""),
                "components": rendered_components
            }
            
        except Exception as e:
            self.logger.error(f"Error rendering template: {str(e)}")
            return None