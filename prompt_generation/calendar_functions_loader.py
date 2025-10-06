"""
Calendar Functions Loader
Loads and formats calendar function definitions for prompt generation
"""

import json
import os
import sys

# Add the CalendarCode directory to path to import function definitions
sys.path.append(os.path.join(os.path.dirname(__file__), 'CalendarCode'))

try:
    from calendar_function_definitions import (
        calendar_book_appointment_function,
        calendar_cancel_appointment_function,
        calendar_reschedule_appointment_function,
        calendar_find_appointment_function,
        calendar_check_available_slots_function
    )
except ImportError as e:
    print(f"Warning: Could not import calendar functions: {e}")
    # Fallback empty definitions
    calendar_book_appointment_function = {}
    calendar_cancel_appointment_function = {}
    calendar_reschedule_appointment_function = {}
    calendar_find_appointment_function = {}
    calendar_check_available_slots_function = {}

def get_calendar_functions_json():
    """Get calendar functions formatted as JSON for prompt generation"""
    functions = [
        calendar_book_appointment_function,
        calendar_cancel_appointment_function,
        calendar_reschedule_appointment_function,
        calendar_find_appointment_function,
        calendar_check_available_slots_function
    ]
    
    # Filter out empty functions
    functions = [f for f in functions if f]
    
    return json.dumps(functions, indent=2)

def get_calendar_instructions():
    """Get calendar-specific instructions for system prompt"""
    return """
## CALENDAR BOOKING TOOLS

You have access to the following calendar management functions:

### Available Functions:
- calendar_book_appointment: Book a new appointment slot
- calendar_cancel_appointment: Cancel an existing appointment  
- calendar_reschedule_appointment: Move an appointment to a new time
- calendar_find_appointment: Search for existing appointments
- calendar_check_available_slots: Check available time slots
- handover_transfer_call: Transfer calls to human agents or departments

### Tool Usage Rules:
**DO:**
- Use tool call preambles: "Let me check that for you", "Let me book that appointment"
- Transform natural language dates/times to ISO format before calling functions
- Always use service provider email as the calendar identifier
- Be proactive - don't ask for permission to use tools
- Handle date/time parsing: "tomorrow" to proper ISO date, "10 AM" to "10:00"
- Always confirm appointment details after booking, rescheduling, or canceling
- Use handover_transfer_call function for ALL escalations and transfers

**DON'T:**
- Ask "Would you like me to..." before using calendar functions
- Use calendar functions without proper date/time formatting
- Book appointments without checking for conflicts first
- Book appointments outside business hours or on doctor's days off
- Simulate or assume transfers without calling handover_transfer_call function
- Include JSON function definitions in system instructions

### Conversation Flow for Appointments:
1. **Information Gathering**: Collect service provider, date, time, customer name
2. **Conflict Check**: Use calendar_find_appointment to check for existing bookings
3. **Action**: Book, reschedule, or cancel as requested
4. **Confirmation**: Provide clear confirmation with appointment details
"""

def update_service_provider_references(text: str) -> str:
    """Update doctor-specific references to generic service provider terms"""
    replacements = {
        'doctor_email': 'service_provider_email',
        'patient_name': 'customer_name',
        'Email address of the doctor': 'Email address of the service provider',
        'Email of the doctor': 'Email of the service provider',
        'doctor with whom': 'service provider with whom',
        "doctor's calendar": "service provider's calendar"
    }
    
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    
    return result

def get_generic_calendar_functions_json():
    """Get calendar functions with generic service provider terminology"""
    functions_json = get_calendar_functions_json()
    return update_service_provider_references(functions_json)

def get_generic_calendar_instructions():
    """Get calendar instructions with generic service provider terminology"""
    instructions = get_calendar_instructions()
    return update_service_provider_references(instructions)
