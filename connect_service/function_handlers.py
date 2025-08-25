"""
Function handlers for Gemini Live API function calling in the connect-service module.
This file contains the implementation of handlers for functions defined in function_definitions.py.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("connect_service.function_handlers")

class FunctionHandlers:
    """
    Class to handle function calls from Gemini Live API.
    Each function defined in function_definitions.py has a corresponding handler method here.
    """
    
    def __init__(self, session=None):
        """
        Initialize the function handlers with an optional Gemini session.
        
        Args:
            session: The Gemini session to use for sending responses back to the model
        """
        self.session = session
        self.call_ended = False
        # Mock database for demonstration purposes
        self._mock_customer_db = {
            "+919876543210": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "previous_appointments": ["2023-06-15", "2023-07-20"]
            },
            "+918765432109": {
                "name": "Jane Smith",
                "email": "jane.smith@example.com",
                "previous_appointments": ["2023-08-05"]
            }
        }
        # Mock calendar for demonstration purposes
        self._mock_calendar = {
            "2023-12-01": {
                "10:00": "Available",
                "10:30": "Available",
                "11:00": "Booked",
                "11:30": "Booked",
                "12:00": "Available"
            },
            "2023-12-02": {
                "10:00": "Booked",
                "10:30": "Available",
                "11:00": "Available",
                "11:30": "Available",
                "12:00": "Booked"
            }
        }
    
    def set_session(self, session):
        """
        Set the Gemini session to use for sending responses.
        
        Args:
            session: The Gemini session
        """
        self.session = session
    
    def is_call_ended(self) -> bool:
        """
        Check if the call has been ended.
        
        Returns:
            bool: True if the call has ended, False otherwise
        """
        return self.call_ended
    
    async def transfer_to_manager(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the transfer_to_manager function call.
        
        Args:
            params: Parameters for the function call
                - customer_request: The customer's request that triggered the transfer
                - handover_reason: The reason for transferring to a manager
        
        Returns:
            Dict[str, Any]: Result of the function call
        """
        try:
            customer_request = params.get('customer_request', '')
            handover_reason = params.get('handover_reason', 'Escalation')
            
            logger.info(f"Transfer to manager requested. Reason: {handover_reason}")
            logger.info(f"Customer request: {customer_request}")
            
            # Prepare handover data that could be used by an external system
            handover_data = {
                'handover_requested': 'Yes',
                'handover_phrase_used': customer_request,
                'handover_reason': handover_reason,
                'handover_to': 'Manager',
                'handover_number': '+919876543210'  # Example manager number
            }
            
            # If we have a session, send a response to the user
            if self.session:
                response_text = "I'm transferring your call to a manager who can better assist you with this. Please hold while I connect you."
                await self.session.send_model_content(turns={"parts": [{"text": response_text}]}, turn_complete=True)
                
                # Set the call as ended to stop the audio loop
                self.call_ended = True
                
                return {
                    "success": True, 
                    "message": "Call transferred to manager", 
                    "handover_data": handover_data
                }
            else:
                logger.error("Session not available for transfer_to_manager")
                return {"success": False, "message": "Session not available"}
                
        except Exception as e:
            logger.error(f"Error in transfer_to_manager: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def lookup_customer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the lookup_customer function call.
        
        Args:
            params: Parameters for the function call
                - phone_number: The customer's phone number to search for
                - name: The customer's name to search for
        
        Returns:
            Dict[str, Any]: Result of the function call with customer information
        """
        try:
            phone_number = params.get('phone_number', '')
            name = params.get('name', '')
            
            logger.info(f"Looking up customer. Phone: {phone_number}, Name: {name}")
            
            # Search by phone number first (more reliable)
            if phone_number and phone_number in self._mock_customer_db:
                customer_data = self._mock_customer_db[phone_number]
                return {
                    "success": True,
                    "customer_found": True,
                    "customer_data": customer_data
                }
            
            # If no phone match, try name match (less reliable)
            if name:
                for phone, data in self._mock_customer_db.items():
                    if name.lower() in data["name"].lower():
                        return {
                            "success": True,
                            "customer_found": True,
                            "customer_data": data,
                            "phone_number": phone
                        }
            
            # No customer found
            return {
                "success": True,
                "customer_found": False,
                "message": "No customer found with the provided information"
            }
                
        except Exception as e:
            logger.error(f"Error in lookup_customer: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def create_appointment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the create_appointment function call.
        
        Args:
            params: Parameters for the function call
                - customer_name: The customer's full name
                - phone_number: The customer's phone number
                - date: The date for the appointment (YYYY-MM-DD)
                - time: The time for the appointment (HH:MM)
                - service_type: The type of service requested
                - notes: Additional notes (optional)
        
        Returns:
            Dict[str, Any]: Result of the function call
        """
        try:
            customer_name = params.get('customer_name', '')
            phone_number = params.get('phone_number', '')
            date = params.get('date', '')
            time = params.get('time', '')
            service_type = params.get('service_type', '')
            notes = params.get('notes', '')
            
            logger.info(f"Creating appointment for {customer_name} on {date} at {time}")
            
            # Check if the date and time are available
            if date in self._mock_calendar and time in self._mock_calendar[date]:
                if self._mock_calendar[date][time] == "Available":
                    # Book the appointment
                    self._mock_calendar[date][time] = "Booked"
                    
                    # Generate a mock appointment ID
                    appointment_id = f"APT-{date.replace('-', '')}-{time.replace(':', '')}"
                    
                    # Add customer to database if not exists
                    if phone_number not in self._mock_customer_db:
                        self._mock_customer_db[phone_number] = {
                            "name": customer_name,
                            "email": "",
                            "previous_appointments": []
                        }
                    
                    # Add this appointment to customer's history
                    self._mock_customer_db[phone_number]["previous_appointments"].append(date)
                    
                    # Create appointment details
                    appointment_details = {
                        "id": appointment_id,
                        "customer_name": customer_name,
                        "phone_number": phone_number,
                        "date": date,
                        "time": time,
                        "service_type": service_type,
                        "notes": notes
                    }
                    
                    # If we have a session, send a confirmation to the user
                    if self.session:
                        response_text = f"Great! I've booked your appointment for {service_type} on {date} at {time}. Your appointment ID is {appointment_id}."
                        await self.session.send_model_content(turns={"parts": [{"text": response_text}]}, turn_complete=True)
                    
                    return {
                        "success": True,
                        "appointment_created": True,
                        "appointment_details": appointment_details
                    }
                else:
                    return {
                        "success": True,
                        "appointment_created": False,
                        "message": f"The requested time slot ({time} on {date}) is already booked."
                    }
            else:
                return {
                    "success": True,
                    "appointment_created": False,
                    "message": f"The requested date ({date}) or time ({time}) is not available."
                }
                
        except Exception as e:
            logger.error(f"Error in create_appointment: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def check_availability(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the check_availability function call.
        
        Args:
            params: Parameters for the function call
                - date: Single date to check (YYYY-MM-DD)
                - start_date: Start of date range (YYYY-MM-DD)
                - end_date: End of date range (YYYY-MM-DD)
        
        Returns:
            Dict[str, Any]: Result of the function call with available slots
        """
        try:
            date = params.get('date', '')
            start_date = params.get('start_date', '')
            end_date = params.get('end_date', '')
            
            available_slots = {}
            
            # Check a single date
            if date:
                logger.info(f"Checking availability for date: {date}")
                if date in self._mock_calendar:
                    available_slots[date] = {
                        time: status for time, status in self._mock_calendar[date].items() 
                        if status == "Available"
                    }
            
            # Check a date range
            elif start_date and end_date:
                logger.info(f"Checking availability from {start_date} to {end_date}")
                # Convert string dates to datetime objects
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                
                # Iterate through the date range
                current = start
                while current <= end:
                    current_str = current.strftime("%Y-%m-%d")
                    if current_str in self._mock_calendar:
                        available_slots[current_str] = {
                            time: status for time, status in self._mock_calendar[current_str].items() 
                            if status == "Available"
                        }
                    current += timedelta(days=1)
            
            # If we have a session, send a summary to the user
            if self.session and available_slots:
                response_text = "Here are the available appointment slots:\n"
                for date, times in available_slots.items():
                    response_text += f"\nDate: {date}\n"
                    for time in times:
                        response_text += f"- {time}\n"
                await self.session.send_model_content(turns={"parts": [{"text": response_text}]}, turn_complete=True)
            
            return {
                "success": True,
                "available_slots": available_slots
            }
                
        except Exception as e:
            logger.error(f"Error in check_availability: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def send_confirmation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the send_confirmation function call.
        
        Args:
            params: Parameters for the function call
                - phone_number: The customer's phone number
                - message_type: Type of message to send
                - appointment_id: ID of the appointment (optional)
                - custom_message: Custom message content (optional)
        
        Returns:
            Dict[str, Any]: Result of the function call
        """
        try:
            phone_number = params.get('phone_number', '')
            message_type = params.get('message_type', '')
            appointment_id = params.get('appointment_id', '')
            custom_message = params.get('custom_message', '')
            
            logger.info(f"Sending {message_type} confirmation to {phone_number}")
            
            # Prepare the message based on type
            message = ""
            if message_type == "appointment_confirmation" and appointment_id:
                # In a real system, we would look up the appointment details
                message = f"Your appointment (ID: {appointment_id}) has been confirmed. Thank you for booking with us!"
            elif message_type == "reminder" and appointment_id:
                message = f"This is a reminder about your upcoming appointment (ID: {appointment_id}). We look forward to seeing you!"
            elif message_type == "custom" and custom_message:
                message = custom_message
            else:
                message = "Thank you for contacting us. We appreciate your business!"
            
            # In a real system, we would send the message via SMS or WhatsApp
            # For now, we'll just log it and return success
            logger.info(f"Message to {phone_number}: {message}")
            
            # If we have a session, inform the user
            if self.session:
                response_text = f"I've sent a confirmation message to {phone_number}."
                await self.session.send_model_content(turns={"parts": [{"text": response_text}]}, turn_complete=True)
            
            return {
                "success": True,
                "message_sent": True,
                "recipient": phone_number,
                "message_content": message
            }
                
        except Exception as e:
            logger.error(f"Error in send_confirmation: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}

# For testing purposes
if __name__ == "__main__":
    handlers = FunctionHandlers()
    print("Function handlers initialized for testing")
