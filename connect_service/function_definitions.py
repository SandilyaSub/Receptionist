"""
Function definitions for Gemini Live API function calling in the connect-service module.
This file contains JSON schema definitions for functions that can be called by Gemini Live API.
"""

import json
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from google.generativeai.types import Tool

def get_transfer_to_manager_definition() -> Dict[str, Any]:
    """
    Define the schema for the transfer_to_manager function.
    This function allows Gemini to transfer a call to a manager when needed.
    
    Returns:
        Dict[str, Any]: JSON schema definition for the transfer_to_manager function
    """
    return {
        "name": "transfer_to_manager",
        "description": "Transfer the current call to a manager when the customer requests it or when the AI cannot handle the request.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_request": {
                    "type": "string",
                    "description": "The customer's request or statement that triggered the transfer"
                },
                "handover_reason": {
                    "type": "string",
                    "description": "The reason for transferring to a manager (e.g., 'Complex issue', 'Customer request', 'Escalation needed')"
                }
            },
            "required": ["customer_request", "handover_reason"]
        }
    }

def get_lookup_customer_definition() -> Dict[str, Any]:
    """
    Define the schema for the lookup_customer function.
    This function allows Gemini to look up customer information in the database.
    
    Returns:
        Dict[str, Any]: JSON schema definition for the lookup_customer function
    """
    return {
        "name": "lookup_customer",
        "description": "Look up a customer's information in the database by phone number or name",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "The customer's phone number to search for"
                },
                "name": {
                    "type": "string",
                    "description": "The customer's name to search for"
                }
            },
            "required": []  # At least one of phone_number or name should be provided, but not enforced in schema
        }
    }

def get_create_appointment_definition() -> Dict[str, Any]:
    """
    Define the schema for the create_appointment function.
    This function allows Gemini to create a new appointment in the calendar.
    
    Returns:
        Dict[str, Any]: JSON schema definition for the create_appointment function
    """
    return {
        "name": "create_appointment",
        "description": "Create a new appointment in the calendar system",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "The customer's full name"
                },
                "phone_number": {
                    "type": "string",
                    "description": "The customer's phone number"
                },
                "date": {
                    "type": "string",
                    "description": "The date for the appointment in YYYY-MM-DD format"
                },
                "time": {
                    "type": "string",
                    "description": "The time for the appointment in HH:MM format (24-hour)"
                },
                "service_type": {
                    "type": "string",
                    "description": "The type of service requested"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes or special requests for the appointment"
                }
            },
            "required": ["customer_name", "phone_number", "date", "time", "service_type"]
        }
    }

def get_check_availability_definition() -> Dict[str, Any]:
    """
    Define the schema for the check_availability function.
    This function allows Gemini to check available appointment slots.
    
    Returns:
        Dict[str, Any]: JSON schema definition for the check_availability function
    """
    return {
        "name": "check_availability",
        "description": "Check available appointment slots for a specific date or date range",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "The date to check availability for in YYYY-MM-DD format"
                },
                "start_date": {
                    "type": "string",
                    "description": "The start date of a range to check in YYYY-MM-DD format"
                },
                "end_date": {
                    "type": "string",
                    "description": "The end date of a range to check in YYYY-MM-DD format"
                }
            },
            "required": []  # Either date or both start_date and end_date should be provided
        }
    }

def get_send_confirmation_definition() -> Dict[str, Any]:
    """
    Define the schema for the send_confirmation function.
    This function allows Gemini to send a confirmation message to the customer.
    
    Returns:
        Dict[str, Any]: JSON schema definition for the send_confirmation function
    """
    return {
        "name": "send_confirmation",
        "description": "Send a confirmation message to the customer via SMS or WhatsApp",
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "The customer's phone number to send the confirmation to"
                },
                "message_type": {
                    "type": "string",
                    "description": "The type of message to send (e.g., 'appointment_confirmation', 'reminder', 'custom')"
                },
                "appointment_id": {
                    "type": "string",
                    "description": "The ID of the appointment to reference in the confirmation"
                },
                "custom_message": {
                    "type": "string",
                    "description": "Custom message content if message_type is 'custom'"
                }
            },
            "required": ["phone_number", "message_type"]
        }
    }

def get_all_function_definitions() -> List[Dict[str, Any]]:
    """
    Get all function definitions as a list.
    
    Returns:
        List[Dict[str, Any]]: List of all function definitions
    """
    return [
        get_transfer_to_manager_definition(),
        get_lookup_customer_definition(),
        get_create_appointment_definition(),
        get_check_availability_definition(),
        get_send_confirmation_definition()
    ]

def get_all_tools() -> List[Tool]:
    """
    Get all function definitions wrapped as Gemini Tool objects.
    
    Returns:
        List[Tool]: List of all function definitions as Tool objects
    """
    function_definitions = get_all_function_definitions()
    tools = []
    
    for function_def in function_definitions:
        tool = Tool(
            function_declarations=[function_def]
        )
        tools.append(tool)
    
    return tools

# For debugging purposes
if __name__ == "__main__":
    print(json.dumps(get_all_function_definitions(), indent=2))
