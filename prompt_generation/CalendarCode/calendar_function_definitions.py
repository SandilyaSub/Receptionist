"""
Calendar Function Declarations for Gemini Live API
Defines the function schemas for calendar operations
"""

# Function declaration for booking an appointment
calendar_book_appointment_function = {
    "name": "calendar_book_appointment",
    "description": "Book an appointment slot on the calendar. The appointment will be scheduled for 30 minutes. Accepts natural language date and time inputs like 'tomorrow morning', 'Friday at 10 AM', 'day after tomorrow', etc. and transform to ISO format before invoking the function. Even if you hear appointment in other language, you should invoke this tool function and return the function response in English.",
    "parameters": {
        "type": "object",
        "properties": {
            "doctor_email": {
                "type": "string",
                "description": "Email address of the doctor"
            },
            "patient_name": {
                "type": "string",
                "description": "Full name of the patient"
            },
            "appointment_date": {
                "type": "string",
                "description": "Date for appointment in YYYY-MM-DD format (ISO date). Transform natural language like 'tomorrow', 'day after tomorrow', 'Friday', 'next Monday' to proper ISO date format before calling this function."
            },
            "appointment_time": {
                "type": "string",
                "description": "Time for appointment in HH:MM format (24-hour). Transform natural language like 'morning' -> '09:00', '10 AM' -> '10:00', '2 PM' -> '14:00', 'afternoon' -> '14:00', 'evening' -> '18:00' to proper 24-hour format before calling this function."
            },
            "reason": {
                "type": "string",
                "description": "Reason for the appointment or medical concern (optional)"
            }
        },
        "required": ["doctor_email", "patient_name", "appointment_date", "appointment_time"]
    }
}

# Function declaration for cancelling an appointment
calendar_cancel_appointment_function = {
    "name": "calendar_cancel_appointment",
    "description": "Cancel an existing appointment from the doctor's calendar. Confirm the patient name before cancelling the appointment.",
    "parameters": {
        "type": "object",
        "properties": {
            "doctor_email": {
                "type": "string",
                "description": "Email of the doctor with whom the appointment was booked"
            },
            "patient_name": {
                "type": "string",
                "description": "Name of the patient whose appointment to cancel"
            },
            "appointment_date": {
                "type": "string",
                "description": "Date of the appointment to cancel in YYYY-MM-DD format (ISO date). Transform natural language like 'tomorrow', 'Friday', 'next Monday' to proper ISO date format before calling this function."
            }
        },
        "required": ["doctor_email", "patient_name", "appointment_date"]
    }
}

# Function declaration for rescheduling an appointment
calendar_reschedule_appointment_function = {
    "name": "calendar_reschedule_appointment",
    "description": "Reschedule an existing appointment to a new date and time. Accepts natural language date and time inputs.",
    "parameters": {
        "type": "object",
        "properties": {
            "doctor_email": {
                "type": "string",
                "description": "Email address of the doctor"
            },
            "patient_name": {
                "type": "string",
                "description": "Name of the patient whose appointment to reschedule"
            },
            "old_appointment_date": {
                "type": "string",
                "description": "Current date of the appointment to reschedule in YYYY-MM-DD format (ISO date). Transform natural language like 'tomorrow', 'Friday', 'next Monday' to proper ISO date format before calling this function."
            },
            "new_appointment_date": {
                "type": "string",
                "description": "New date for the appointment in YYYY-MM-DD format (ISO date). Transform natural language like 'tomorrow', 'day after tomorrow', 'Friday', 'next Monday' to proper ISO date format before calling this function."
            },
            "new_appointment_time": {
                "type": "string",
                "description": "New time for the appointment in HH:MM format (24-hour). Transform natural language like 'morning' -> '09:00', '10 AM' -> '10:00', '2 PM' -> '14:00', 'afternoon' -> '14:00', 'evening' -> '18:00' to proper 24-hour format before calling this function."
            }
        },
        "required": ["doctor_email", "patient_name", "old_appointment_date", "new_appointment_date", "new_appointment_time"]
    }
}

# Function declaration for finding appointments
calendar_find_appointment_function = {
    "name": "calendar_find_appointment",
    "description": "Find existing appointments based on the appointment date and patient details in the calendar summary for the doctor_email",
    "parameters": {
        "type": "object",
        "properties": {
            "doctor_email": {
                "type": "string",
                "description": "Email of the doctor with whom the appointment is to be booked"
            },
            "patient_name": {
                "type": "string",
                "description": "Name of the patient to search for in the calendar summary"
            },
            "search_date": {
                "type": "string",
                "description": "Date to search for appointments in YYYY-MM-DD format (ISO date). Transform natural language like 'tomorrow', 'Friday', 'next Monday' to proper ISO date format before calling this function. Optional - if not provided, searches all dates."
            }
        },
        "required": ["doctor_email", "patient_name"]
    }
}

# Function declaration for checking available appointment slots
calendar_check_available_slots_function = {
    "name": "calendar_check_available_slots",
    "description": "Check available appointment slots for a doctor on a specific date from the calendar. This should be called only if there is a conflicting slot with the doctor's calendar. This should return the next available slot based on the working hours for that day. If there are no available slots, return 'No available slots'.",
    "parameters": {
        "type": "object",
        "properties": {
            "doctor_email": {
                "type": "string",
                "description": "Email address of the doctor",
            },
            "date": {
                "type": "string",
                "description": "Date to check for available slots in YYYY-MM-DD format (ISO date). Transform natural language like 'tomorrow', 'Friday', 'next Monday' to proper ISO date format before calling this function."
            }
        },
        "required": ["doctor_email", "date"]
    }
}

# Combine all calendar functions
calendar_functions = [
    calendar_book_appointment_function,
    calendar_cancel_appointment_function,
    calendar_reschedule_appointment_function,
    calendar_find_appointment_function
]
