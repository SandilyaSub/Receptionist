"""
Function definitions for Gemini Live API function calling in the connect-service module.
This file contains JSON schema definitions for functions that can be called by Gemini Live API.
"""

import json
from typing import Dict, List, Any, Optional
from google.genai import types

def get_call_handover_function_definition() -> Dict[str, Any]:
    """
    Define the schema for the call_handover_function.
    This function allows Gemini to transfer a call to a manager when needed.
    
    Returns:
        Dict[str, Any]: JSON schema definition for the call_handover_function
    """
    return {
        "name": "call_handover_function",
        "description": "Transfer the call to a manager when the customer requests escalation or needs to speak with a human",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_request": {
                    "type": "string",
                    "description": "The exact phrase used by the customer to request speaking with a manager or human"
                },
                "handover_reason": {
                    "type": "string",
                    "enum": ["Escalation", "Complex Issue", "Customer Dissatisfaction", "Technical Problem", "Billing Question", "AI Limitation"],
                    "description": "The reason for transferring the call to a manager"
                }
            },
            "required": ["customer_request", "handover_reason"]
        }
    }

def get_all_function_definitions() -> List[Dict[str, Any]]:
    """
    Get all function definitions as a list of dictionaries.
    
    Returns:
        List[Dict[str, Any]]: List of all function definitions
    """
    return [
        get_call_handover_function_definition()
    ]

def get_all_tools() -> List[types.Tool]:
    """
    Get all function definitions wrapped as Gemini Tool objects.
    
    Returns:
        List[types.Tool]: List of all function definitions as Tool objects
    """
    function_definitions = get_all_function_definitions()
    tools = []
    
    for function_def in function_definitions:
        tool = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=function_def['name'],
                    description=function_def['description'],
                    parameters=function_def['parameters']
                )
            ]
        )
        tools.append(tool)
    
    return tools

# For debugging purposes
if __name__ == "__main__":
    print(json.dumps(get_all_function_definitions(), indent=2))
