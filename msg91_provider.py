"""
MSG91 Provider for WhatsApp messaging

This module handles the integration with MSG91 API for sending WhatsApp messages.
"""

import json
import logging
import aiohttp
import traceback
import re
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
        
        # We need to convert pipe-separated messages to proper WhatsApp formatting
        
        # Validate initialization
        if not auth_key:
            self.logger.warning("MSG91 provider initialized without auth_key")
        
    async def send_message(self, to_number: str, template_name: str, 
                          template_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send WhatsApp message via MSG91
        
        Args:
            to_number: Recipient phone number (E.164 format)
            template_name: Name of the WhatsApp template to use
            template_data: Template data containing message_body
            
        Returns:
            Dict[str, Any]: Response object with status, message, and data
                {
                    'status': 'success'|'error',
                    'message': str,  # Human-readable message
                    'data': Any      # Additional response data if any
                }
        """
        if not self.auth_key:
            error_msg = "Cannot send message: MSG91_AUTH_KEY not configured"
            self.logger.error(error_msg)
            return {
                'status': 'error',
                'message': error_msg,
                'data': None
            }
            
        headers = {
            "Content-Type": "application/json",
            "authkey": self.auth_key
        }
        
        # Extract message body from template data
        message_body = template_data.get("message_body", "")
        
        # Ensure message_body is a string, not a dictionary
        if isinstance(message_body, dict):
            self.logger.warning(f"message_body is a dictionary, converting to string: {message_body}")
            try:
                # Try to convert dict to a formatted string
                message_body = json.dumps(message_body, indent=2)
            except Exception as e:
                self.logger.error(f"Error converting dict to string: {str(e)}")
                # Fallback to simple string conversion
                message_body = str(message_body)
                
        if not message_body:
            self.logger.warning(f"No message_body provided for template {template_name}")
            message_body = "Thank you for your inquiry. We'll be in touch soon."
            
        # AI now generates messages with <br> tags for line breaks
        # No formatting needed here
            
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
                            "components": self._prepare_template_components(template_name, template_data)
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
                        return {
                            'status': 'error',
                            'message': f"MSG91 API error: {result}",
                            'data': None
                        }
                    
                    success_msg = f"Message sent successfully to {to_number}"
                    self.logger.info(success_msg)
                    return {
                        'status': 'success',
                        'message': success_msg,
                        'data': result
                    }
                    
        except aiohttp.ClientError as e:
            self.logger.error(f"MSG91 API connection error: {str(e)}")
            return {
                'status': 'error',
                'message': f"MSG91 API connection error: {str(e)}",
                'data': None
            }
        except Exception as e:
            error_msg = f"Error sending MSG91 message: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"Exception traceback: {traceback.format_exc()}")
            return {
                'status': 'error',
                'message': error_msg,
                'data': {'exception': str(e), 'traceback': traceback.format_exc()}
            }
            
    def _prepare_template_components(self, template_name: str, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare template components based on template name
        
        Args:
            template_name: Name of the template (e.g., 'service_message', 'owner_message')
            template_data: Template data with variables
            
        Returns:
            Dict with components formatted for the specific template
        """
        if template_name == "owner_message":
            # For owner_message template with 4 variables
            return {
                "body_1": {
                    "type": "text",
                    "value": template_data.get("var1", "")  # Customer phone
                },
                "body_2": {
                    "type": "text",
                    "value": template_data.get("var2", "")  # Call type
                },
                "body_3": {
                    "type": "text",
                    "value": template_data.get("var3", "")  # Summary
                },
                "body_4": {
                    "type": "text",
                    "value": template_data.get("var4", "")  # Pipe-separated key-value pairs
                }
            }
        else:
            # Default for service_message template with 4 variables
            message_body = template_data.get("message_body", {})
            
            # Handle the case where message_body is already a dictionary with the 4 components
            if isinstance(message_body, dict) and all(key in message_body for key in ["body_1", "body_2", "body_3", "body_4"]):
                self.logger.info("Using structured 4-component message format")
                return {
                    "body_1": {
                        "type": "text",
                        "value": message_body.get("body_1", "there")
                    },
                    "body_2": {
                        "type": "text",
                        "value": message_body.get("body_2", "Thank you for your inquiry.")
                    },
                    "body_3": {
                        "type": "text",
                        "value": message_body.get("body_3", "We've received your message and will follow up shortly.")
                    },
                    "body_4": {
                        "type": "text",
                        "value": message_body.get("body_4", "We look forward to serving you soon!")
                    }
                }
            
            # Handle the case where message_body is a string that might be JSON
            if isinstance(message_body, str) and message_body.strip().startswith('{'):
                try:
                    # Try to parse as JSON
                    parsed_body = json.loads(message_body)
                    if isinstance(parsed_body, dict) and all(key in parsed_body for key in ["body_1", "body_2", "body_3", "body_4"]):
                        self.logger.info("Parsed message_body string as JSON with 4 components")
                        return {
                            "body_1": {
                                "type": "text",
                                "value": parsed_body.get("body_1", "there")
                            },
                            "body_2": {
                                "type": "text",
                                "value": parsed_body.get("body_2", "Thank you for your inquiry.")
                            },
                            "body_3": {
                                "type": "text",
                                "value": parsed_body.get("body_3", "We've received your message and will follow up shortly.")
                            },
                            "body_4": {
                                "type": "text",
                                "value": parsed_body.get("body_4", "We look forward to serving you soon!")
                            }
                        }
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse message_body as JSON, using fallback")
            
            # Fallback for backward compatibility or error cases
            self.logger.warning("Using fallback 4-component message format")
            
            # Convert message_body to string if it's a dict but not in the expected format
            if isinstance(message_body, dict):
                try:
                    message_body = json.dumps(message_body, indent=2)
                except Exception as e:
                    self.logger.error(f"Error converting dict to string: {str(e)}")
                    message_body = str(message_body)
            
            # If message_body is a string, use it as body_3 (the main content)
            if isinstance(message_body, str):
                return {
                    "body_1": {
                        "type": "text",
                        "value": "there"
                    },
                    "body_2": {
                        "type": "text",
                        "value": "Thank you for your inquiry."
                    },
                    "body_3": {
                        "type": "text",
                        "value": message_body or "We've received your message and will follow up shortly."
                    },
                    "body_4": {
                        "type": "text",
                        "value": "We look forward to serving you soon!"
                    }
                }
            
            # Final fallback with empty values
            return {
                "body_1": {
                    "type": "text",
                    "value": "there"
                },
                "body_2": {
                    "type": "text",
                    "value": "Thank you for your inquiry."
                },
                "body_3": {
                    "type": "text",
                    "value": "We've received your message and will follow up shortly."
                },
                "body_4": {
                    "type": "text",
                    "value": "We look forward to serving you soon!"
                }
            }
    # _format_whatsapp_message method removed as we now handle pipe-to-newline conversion in send_message
