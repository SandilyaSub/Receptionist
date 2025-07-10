"""
MSG91 Provider for WhatsApp messaging

This module handles the integration with MSG91 API for sending WhatsApp messages.
"""

import json
import logging
import aiohttp
from typing import Dict, Any, Optional

class MSG91Provider:
    """Provider for sending WhatsApp messages via MSG91 API"""
    
    def __init__(self, auth_key: str, integrated_number: str, logger=None):
        """
        Initialize the MSG91 provider
        
        Args:
            auth_key: MSG91 authentication key
            integrated_number: MSG91 integrated WhatsApp number
            logger: Optional logger instance
        """
        self.auth_key = auth_key
        self.integrated_number = integrated_number
        self.api_url = "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"
        self.logger = logger or logging.getLogger(__name__)
        
        # Validate initialization
        if not auth_key:
            self.logger.warning("MSG91 provider initialized without auth_key")
        
    async def send_message(self, to_number: str, template_name: str, 
                          template_data: Dict[str, Any]) -> bool:
        """
        Send WhatsApp message via MSG91
        
        Args:
            to_number: Recipient phone number (E.164 format)
            template_name: Name of the WhatsApp template to use
            template_data: Template data containing message_body
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.auth_key:
            self.logger.error("Cannot send message: MSG91_AUTH_KEY not configured")
            return False
            
        headers = {
            "Content-Type": "application/json",
            "authkey": self.auth_key
        }
        
        # Extract message body from template data
        message_body = template_data.get("message_body", "")
        if not message_body:
            self.logger.warning(f"No message_body provided for template {template_name}")
            message_body = "Thank you for your inquiry. We'll be in touch soon."
            
        # Construct payload with the exact structure that works in curl command
        payload = {
            "integrated_number": self.integrated_number,
            "content_type": "template",
            "payload": {
                "messaging_product": "whatsapp",
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": "en",
                        "policy": "deterministic"
                    },
                    "namespace": "2e1d8662_869f_48e9_bb1f_5f995acb2c20", # Updated namespace from service_message.json
                    "to_and_components": [
                        {
                            "to": [to_number],
                            "components": {
                                "body_1": {
                                    "type": "text",
                                    "value": message_body
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        try:
            self.logger.debug(f"Sending MSG91 WhatsApp message to {to_number}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url, 
                    headers=headers, 
                    json=payload,
                    timeout=10  # 10 second timeout
                ) as response:
                    response_text = await response.text()
                    
                    try:
                        result = json.loads(response_text)
                    except json.JSONDecodeError:
                        result = {"raw_response": response_text}
                    
                    if response.status != 200:
                        self.logger.error(f"MSG91 API error: {result}")
                        return False
                    
                    self.logger.info(f"Message sent to {to_number}, result: {result}")
                    return True
                    
        except aiohttp.ClientError as e:
            self.logger.error(f"MSG91 API connection error: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error sending MSG91 message: {str(e)}")
            return False
