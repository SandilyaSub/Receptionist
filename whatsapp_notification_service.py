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

# We'll configure Gemini API dynamically when needed

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
        if not os.getenv("GEMINI_API_KEY"):
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
Generate exactly 4 separate text components in this order:

BODY_1:
[Your body_1 content here]

BODY_2:
[Your body_2 content here]

BODY_3:
[Your body_3 content here]

BODY_4:
[Your body_4 content here]

COMPONENT GUIDELINES:

BODY_1: 
- Use customer name if available in critical_call_details
- If no name, use "there" or appropriate greeting
- Just the name/greeting, no additional text

BODY_2:
- Acknowledge the call context with enthusiasm
- Include 1-2 relevant emojis
- Keep it conversational and warm
- Examples: "Just confirmed your cake order - 2 delicious treats coming your way! 🎂", "Thanks for your interest in our digital wedding invitations! 💌"

BODY_3:
- Include ALL critical details from the call
- Format key information clearly
- Use specific details like dates, times, prices, quantities
- Be comprehensive but concise
- Examples: "1kg Dutch Truffle (round) + 0.5kg Butterscotch (square), both eggless. Ready tomorrow at 6 PM!", "2D invitations: ₹1,500-₹2,900 | 3D with caricatures: ₹3,500-₹4,500. 1-day delivery!"

BODY_4:
- Personality-driven closing message
- Include relevant emoji
- Match the business context
- Create anticipation or warmth
- Examples: "We'll have your birthday surprises ready! See you tomorrow! ✨", "Ready to make your special day unforgettable? 🎉"

IMPORTANT RULES:
- Always return exactly 4 components with the BODY_1:, BODY_2:, BODY_3:, BODY_4: labels
- No newlines within individual component content
- Include relevant emojis but don't overuse them
- Match tone to business type (playful for bakery, elegant for invitations, professional for medical)
- ALL critical details must be included in BODY_3
- Keep messages warm, engaging, and professional

BUSINESS CONTEXT ADAPTATION:
- Bakery: Use food emojis (🎂🍰🧁), warm language about treats and celebrations
- Joy Invite: Use celebration emojis (💕🎉💌), romantic/festive language
- Medical: Use professional emojis (🏥🩺), caring but professional tone
- General: Adapt emoji and tone to context

EXAMPLE OUTPUT:
BODY_1:
Sandy

BODY_2:
Just confirmed your cake order - 2 delicious treats coming your way! 🎂

BODY_3:
1kg Dutch Truffle (round) + 0.5kg Butterscotch (square), both eggless as requested. Ready for pickup tomorrow at 6 PM sharp!

BODY_4:
We'll have your birthday surprises wrapped and ready! See you tomorrow! ✨

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
    
    def extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from text that might be wrapped in code fences (triple backticks)
        
        Args:
            text: Text that might contain JSON, possibly wrapped in code fences
            
        Returns:
            Parsed JSON dictionary or None if parsing failed
        """
        try:
            # First, try to parse the text directly as JSON
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
                
            # If that fails, look for code fences
            # Pattern: ```json\n{...}\n``` or ```{...}```
            import re
            json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, text)
            
            if match:
                json_str = match.group(1).strip()
                return json.loads(json_str)
                
            return None
        except Exception as e:
            self.logger.error(f"Error extracting JSON from text: {str(e)}")
            return None
    
    def parse_labeled_components(self, text: str) -> Dict[str, str]:
        """
        Parse labeled components from text
        
        Args:
            text: Text to parse
            
        Returns:
            Dictionary with labeled components
        """
        # First, try to extract JSON from the text
        json_components = self.extract_json_from_text(text)
        if json_components:
            self.logger.info(f"Successfully extracted JSON components: {json_components}")
            # Convert all values to strings if they aren't already
            return {k: str(v) for k, v in json_components.items()}
            
        # If JSON extraction fails, fall back to the original parsing logic
        components = {
            "body_1": "",
            "body_2": "",
            "body_3": "",
            "body_4": ""
        }
        
        # Split text into lines for parsing
        lines = text.strip().split('\n')
        
        current_component = None
        component_content = []
        
        for line in lines:
            line = line.strip()
            
            # Check for component labels
            if line.upper().startswith("BODY_1:"):
                current_component = "body_1"
                # Extract content after the label
                content = line[len("BODY_1:"):].strip()
                if content:
                    component_content.append(content)
            elif line.upper().startswith("BODY_2:"):
                # Save previous component if we were collecting one
                if current_component and component_content:
                    components[current_component] = " ".join(component_content)
                    component_content = []
                
                current_component = "body_2"
                content = line[len("BODY_2:"):].strip()
                if content:
                    component_content.append(content)
            elif line.upper().startswith("BODY_3:"):
                if current_component and component_content:
                    components[current_component] = " ".join(component_content)
                    component_content = []
                    
                current_component = "body_3"
                content = line[len("BODY_3:"):].strip()
                if content:
                    component_content.append(content)
            elif line.upper().startswith("BODY_4:"):
                if current_component and component_content:
                    components[current_component] = " ".join(component_content)
                    component_content = []
                    
                current_component = "body_4"
                content = line[len("BODY_4:"):].strip()
                if content:
                    component_content.append(content)
            elif current_component:
                # Add this line to the current component's content
                component_content.append(line)
        
        # Save the last component if we were collecting one
        if current_component and component_content:
            components[current_component] = " ".join(component_content)
        
        return components

    def validate_message_components(self, components: Dict[str, str]) -> Dict[str, str]:
        """
        Validate message components and provide defaults for missing ones.
        
        Args:
            components: Dictionary with the message components
            
        Returns:
            Validated dictionary with all required components
        """
        # Default values for missing components
        if not components.get("body_1"):
            components["body_1"] = "there"
        if not components.get("body_2"):
            components["body_2"] = "Thank you for your inquiry."
        if not components.get("body_3"):
            components["body_3"] = "We've received your message and will follow up shortly."
        if not components.get("body_4"):
            components["body_4"] = "We look forward to serving you soon!"
        
        return components

    def default_message_components(self) -> Dict[str, str]:
        """
        Return default message components for fallback situations.
        
        Returns:
            Dictionary with default message components
        """
        return {
            "body_1": "there",
            "body_2": "Thank you for your inquiry.",
            "body_3": "We've received your message and will follow up shortly.",
            "body_4": "We look forward to serving you soon!"
        }
        
    async def generate_ai_message(self, call_type: str, critical_call_details: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate WhatsApp message components using Gemini Flash 2.5
        
        Args:
            call_type: Type of call (e.g., "Booking", "Informational")
            critical_call_details: Details extracted from the call
            
        Returns:
            Dictionary with 4 body components
        """
        # Get API key dynamically from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.logger.error("Cannot generate message: GEMINI_API_KEY not configured")
            return self.default_message_components()
            
        # Use the class attribute for system instruction defined in __init__
        self.logger.info("Using 4-component labeled format for customer notification")        
        try:
            # Use the genai package with the correct syntax
            client = genai.Client(api_key=api_key)
            
            # Prepare details string for the prompt
            details_str = ""
            if critical_call_details:
                if isinstance(critical_call_details, str):
                    details_str = critical_call_details
                else:
                    for key, value in critical_call_details.items():
                        details_str += f"{key}: {value}\n"
            
            # Create a structured prompt that asks for labeled components
            prompt = f"""
            Create a WhatsApp notification message for a {call_type} call with the following details:
            
            {details_str}
            
            Remember to provide exactly 4 separate text components labeled as BODY_1, BODY_2, BODY_3, and BODY_4 as specified in the system instructions.
            """
            
            self.logger.info(f"Sending prompt to Gemini API:\n{prompt}")
            
            # Configure the generation parameters using the proper types.GenerateContentConfig
            # Set up system instruction and generation config
            try:
                # Create proper configuration according to Gemini API documentation
                config = types.GenerateContentConfig(
                    temperature=0.7,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=1024,
                    system_instruction=self.ai_system_instruction
                )
                
                # Send the prompt to Gemini with proper configuration
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=config
                )
            except Exception as e:
                self.logger.error(f"Error during Gemini API call configuration: {str(e)}")
                # Fallback to simpler configuration if the above fails
                config = types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=1024,
                )
                
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"{self.ai_system_instruction}\n\n{prompt}",
                    config=config
                )
            
            self.logger.info(f"Raw Gemini API response: {response}")
            
            # Extract text from the response
            response_text = response.text
                    
            self.logger.info(f"AI generated message: {response_text}")
            
            # Parse the labeled components (now with JSON extraction support)
            message_components = self.parse_labeled_components(response_text)
            
            # Validate and provide defaults for missing components
            message_components = self.validate_message_components(message_components)
            
            self.logger.info(f"Generated message components: {json.dumps(message_components, indent=2)}")
            return message_components
                
        except Exception as e:
            self.logger.error(f"Error generating AI message: {str(e)}")
            self.logger.exception("Full exception details:")
            # Fallback message in case of error
            return self.default_message_components()
    
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
