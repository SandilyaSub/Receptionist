#!/usr/bin/env python3
"""
Comprehensive calendar event management system for voiceagent4web@gmail.com
Includes functions for creating, rescheduling, canceling, and detecting conflicts

LOGGING STRATEGY:
This service has comprehensive logging to help debug issues:
- 🔧 Constructor and initialization logging
- 🔐 OAuth token and credentials logging  
- 🔍 API call parameter and response logging
- ❌ Error logging with detailed context
- ✅ Success logging for key operations

The logging helps identify:
1. OAuth token issues (expired, invalid, missing)
2. Google Calendar API call failures
3. Database connection issues
4. Parameter validation problems
5. Service initialization failures
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from sqlmodel import Session, select
import uuid
import pytz
from app.models.ai_agent_tool import AIAgentTool
import logging

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import get_session
# from app.models.tool import AIAgentTool
# from app.models.ai_agent import AIAgent
# from app.models.tool import Tool

logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

class CalendarService:
    def __init__(self, agent_id:uuid.UUID, from_number: str, tool_id:uuid.UUID, call_sid:str):
        self.agent_id = agent_id
        self.from_number = from_number
        self.tool_id = tool_id
        self.call_sid = call_sid
        logger.info(f"🔧 Initializing CalendarService for agent_id: {agent_id}, from_number: {from_number}")
        
        self.credentials = self.get_credentials()
        logger.info(f"🔧 Credentials obtained: {self.credentials is not None}")
        
        if self.credentials:
            try:
                self.service = build('calendar', 'v3', credentials=self.credentials)
                logger.info(f"🔧 Google Calendar service built successfully")
            except Exception as build_error:
                logger.error(f"❌ Error building Google Calendar service: {build_error}")
                self.service = None
        else:
            logger.error(f"❌ No credentials available, service will be None")
            self.service = None
            
        self.calendar_id = 'primary'
        logger.info(f"🔧 CalendarService initialization complete, service available: {self.service is not None}")

    def book_appointment(self, event_details: dict):
        """Create a calendar event using Google Calendar API"""
        
        # Check if service is available (OAuth token is valid)
        if not self.service:
            logger.error("❌ Google Calendar service not available. OAuth token may be invalid or missing.")
            return {
                "success": False,
                "error": "OAuth token invalid or missing",
                "message": "Please re-authenticate to access Google Calendar"
            }

        doctor_email = event_details.get('doctor_email')
        patient_name = event_details.get('patient_name')
        appointment_date = event_details.get('appointment_date')
        appointment_time = event_details.get('appointment_time')
        reason = event_details.get('reason', 'No reason provided')

        # Check if there is existing appointment for the same doctor and patient on the same date and time
        logger.info(f"🔍 Checking for existing appointments with details: {event_details}")
        appointments = self.find_appointment(event_details)
        logger.info(f"🔍 find_appointment returned: {appointments}")
        
        if appointments is None:
            logger.error("❌ find_appointment returned None - this indicates an exception occurred")
            return {
                "success": False,
                "error": "Internal error",
                "message": "Error checking for existing appointments. Please try again."
            }
            
        if appointments['events_found'] > 0:
            logger.info(f"❌ Appointment already exists for {patient_name} on {appointment_date} at {appointment_time}")
            return {
                "success": False,
                "error": appointments['booked_by'],
                "message": appointments['message']
            }

        # Calculate end time (30 minutes after start time)
        start_datetime = datetime.strptime(appointment_date + ' ' + appointment_time, '%Y-%m-%d %H:%M')
        end_datetime = start_datetime + timedelta(minutes=30)
        
        # Format for Google Calendar API (RFC3339 format with timezone)
        start_iso = start_datetime.strftime('%Y-%m-%dT%H:%M:%S')
        end_iso = end_datetime.strftime('%Y-%m-%dT%H:%M:%S')

        # Create event description
        data = {
            'summary': f'Appointment for {patient_name}. Booked by {self.from_number}',
            'description': reason,
            'start': {
                'dateTime': start_iso,
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_iso,
                'timeZone': 'Asia/Kolkata',
            },
            'attendees': [
                {
                    'email': doctor_email,
                    'responseStatus': 'accepted'  # Explicitly set as accepted
                },
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                    {'method': 'popup', 'minutes': 30},       # 30 minutes before
                ],
            },
        }

        try:
            # Build the Google Calendar service
            service = build('calendar', 'v3', credentials=self.credentials)
            
            # Create the event
            try:
                event = service.events().insert(
                    calendarId=doctor_email,
                    body=data
                ).execute()
                logger.info(f"✅ Event created successfully!")
            except Exception as api_error:
                logger.error(f"❌ Error creating event: {api_error}")
                logger.error(f"❌ Event data: {data}")
                raise api_error
            logger.info(f"Event ID: {event['id']}")
            logger.info(f"Event Link: {event['htmlLink']}")
            return event
            
        except Exception as e:
            logger.info(f"❌ Error creating calendar event: {e}")
            return None

    def find_appointment(self, event_details: dict, is_rescheduling: bool = False):
        """Find an appointment for a doctor on a specific date"""
        try:
            # Check if service is available (OAuth token is valid)
            if not self.service:
                logger.error("❌ Google Calendar service not available. OAuth token may be invalid or missing.")
                return {
                    "events_found": 0,
                    "booked_by": None,
                    "event_id": None,
                    "message": "Please re-authenticate to access Google Calendar"
                }
            
            doctor_email = event_details.get('doctor_email')
            appointment_date = event_details.get('appointment_date')
            appointment_time = event_details.get('appointment_time')

            # -------------------------- OLD APPOINTMENT LOGIC --------------------------

            """
            Check for existing appointment 
                - If found, then check for conflict
                    - If there a conflict at 9am
                        - Choose other time
                - If not found, then book for the new slot
            """
            if is_rescheduling:
                # For rescheduling, search in primary calendar for user's events, then filter by doctor
                search_params = {
                    'calendarId': doctor_email,
                    'singleEvents': True,
                    'orderBy': 'startTime',
                    'q': self.from_number
                }
                target_date = datetime.strptime(appointment_date, '%Y-%m-%d')
                time_min = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                time_max = target_date.replace(hour=23, minute=59, second=59, microsecond=0)
                search_params['timeMin'] = time_min.isoformat() + 'Z'
                search_params['timeMax'] = time_max.isoformat() + 'Z'

                existing_appointments = self.service.events().list(**search_params).execute()
                existing_events = existing_appointments.get('items', [])

                if existing_events:
                    appointment = existing_events[0]
                    logger.info(f"🔍 User has existing booking at {appointment_time} on {appointment_date}")
                    # Check for conflict
                    new_appointment_date = event_details.get('new_appointment_date')
                    new_appointment_time = event_details.get('new_appointment_time')
                    
                    if not new_appointment_date or not new_appointment_time:
                        return {
                            "events_found": len(existing_events),
                            "booked_by": self.from_number,
                            "event_id": existing_events[0]['id'],
                            "message": "No new appointment details provided for rescheduling."
                        }
                    
                    target_date = datetime.strptime(new_appointment_date, '%Y-%m-%d')
                    target_time = datetime.strptime(new_appointment_time, '%H:%M')
                    time_min = target_date.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
                    # Add 30 minutes properly to avoid minute overflow
                    end_datetime = time_min + timedelta(minutes=30)
                    time_max = end_datetime
                    new_search_params = {
                        'calendarId': doctor_email,  # Use primary calendar for conflict detection
                        'singleEvents': True,
                        'orderBy': 'startTime'
                    }
                    new_search_params['timeMin'] = time_min.strftime('%Y-%m-%dT%H:%M:%S+05:30')
                    new_search_params['timeMax'] = time_max.strftime('%Y-%m-%dT%H:%M:%S+05:30')
                    try:
                        conflicting_events = self.service.events().list(**new_search_params).execute()
                        logger.info(f"🔍 Conflict check API response: {conflicting_events}")
                    except Exception as api_error:
                        logger.error(f"❌ Error calling Google Calendar API for conflict check: {api_error}")
                        logger.error(f"❌ API call params: {new_search_params}")
                        raise api_error
                        
                    conflicting_events_list = conflicting_events.get('items', [])
                    if conflicting_events_list:
                        # Filter events to only include those with the specific doctor as attendee
                        doctor_specific_conflicts = []
                        for event in conflicting_events_list:
                            attendees = event.get('attendees', [])
                            for attendee in attendees:
                                if attendee.get('email') == doctor_email:
                                    doctor_specific_conflicts.append(event)
                                    break
                        
                        if doctor_specific_conflicts:
                            conflicting_event = doctor_specific_conflicts[0]
                            return {
                                "events_found": len(doctor_specific_conflicts),
                                "event_id": conflicting_event['id'],
                                "booked_by": conflicting_event['summary'],
                                "message": "Sorry, there is another appointment at the specified time. Would you like to pick another slot ?"
                            }
                    else:
                        return {
                            "events_found": len(existing_events),
                            "booked_by": self.from_number,
                            "event_id": existing_events[0]['id'],
                            "message": "No appointment found at the specified time. Do you want me to book this slot ?"
                        }
                    
                return {
                    "events_found": len(existing_events),
                    "booked_by": None,
                    "event_id": None,
                    "message": "No appointment found for this user to reschedule. Do you want me to book a new appointment ?"
                }
                

            # -------------------------- NEW APPOINTMENT LOGIC --------------------------

            # Use the primary calendar for conflict detection but filter by doctor as attendee
            # This ensures we check conflicts in the primary calendar where appointments are actually stored
            search_params = {
                'calendarId': doctor_email,
                'singleEvents': True,
                'orderBy': 'startTime'
            }

            """
            Check for conflict
            1. if there a conflict
                    - If yes, ask user to choose other time
            2. If not conflict, then check if the user has existing booking
                    If yes, ask user to reschedule
                    If no, then book the appointment
            """

            # Check for conflict based on date and time
            if appointment_date:
                target_date = datetime.strptime(appointment_date, '%Y-%m-%d')
                target_time = datetime.strptime(appointment_time, '%H:%M')
                # Check for overlapping time slots, not just exact matches
                # Expand search window to catch overlapping appointments
                time_min = target_date.replace(hour=0, minute=0, second=0, microsecond=0)  # Start of day
                time_max = target_date.replace(hour=23, minute=59, second=59, microsecond=0)  # End of day
                # Use IST timezone instead of UTC to match appointment creation
                search_params['timeMin'] = time_min.strftime('%Y-%m-%dT%H:%M:%S+05:30')
                search_params['timeMax'] = time_max.strftime('%Y-%m-%dT%H:%M:%S+05:30')
            
            logger.info(f"🔍 Search params for finding appointments: {search_params}")

            try:
                events_result = self.service.events().list(**search_params).execute()
                logger.info(f"🔍 Google Calendar API response: {events_result}")
            except Exception as api_error:
                logger.error(f"❌ Error calling Google Calendar API: {api_error}")
                logger.error(f"❌ API call params: {search_params}")
                raise api_error
                
            events = events_result.get('items', [])

            logger.info(f"🔍 Finding appointments at {appointment_time} on {appointment_date}")
            logger.info(f"🔍 Found {len(events)} appointments")
            logger.info(f"🔍 Events: {events}")

            # Check for overlapping time slots with existing appointments
            if events:
                # Filter events to only include those with the specific doctor as attendee
                doctor_specific_events = []
                for event in events:
                    attendees = event.get('attendees', [])
                    for attendee in attendees:
                        if attendee.get('email') == doctor_email:
                            doctor_specific_events.append(event)
                            break
                
                if doctor_specific_events:
                    # Check for actual time overlaps with the requested slot
                    requested_start = target_date.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
                    requested_end = requested_start + timedelta(minutes=30)
                    
                    overlapping_events = []
                    for event in doctor_specific_events:
                        event_start_str = event['start'].get('dateTime')
                        event_end_str = event['end'].get('dateTime')
                        
                        if event_start_str and event_end_str:
                            try:
                                # Parse event times (handle both 'Z' and '+05:30' formats)
                                if event_start_str.endswith('Z'):
                                    event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                                else:
                                    event_start = datetime.fromisoformat(event_start_str)
                                
                                if event_end_str.endswith('Z'):
                                    event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                                else:
                                    event_end = datetime.fromisoformat(event_end_str)
                                
                                # Convert to IST for comparison
                                ist = pytz.timezone('Asia/Kolkata')
                                event_start_ist = event_start.astimezone(ist).replace(tzinfo=None)
                                event_end_ist = event_end.astimezone(ist).replace(tzinfo=None)
                                
                                logger.info(f"🔍 Parsed event times: {event_start_str} -> {event_start_ist.strftime('%H:%M')}, {event_end_str} -> {event_end_ist.strftime('%H:%M')}")
                            except Exception as parse_error:
                                logger.error(f"❌ Error parsing event times: {parse_error}")
                                logger.error(f"❌ Event start: {event_start_str}, Event end: {event_end_str}")
                                continue
                            
                            # Check for overlap: (start1 < end2) and (end1 > start2)
                            if (requested_start < event_end_ist) and (requested_end > event_start_ist):
                                overlapping_events.append(event)
                                logger.info(f"🔍 Found overlapping appointment: {event_start_ist.strftime('%H:%M')} - {event_end_ist.strftime('%H:%M')} conflicts with requested {requested_start.strftime('%H:%M')} - {requested_end.strftime('%H:%M')}")
                    
                    if overlapping_events:
                        logger.info(f"🔍 Found {len(overlapping_events)} overlapping appointments for {doctor_email} at {appointment_time} on {appointment_date}")
                        return {
                            "events_found": len(overlapping_events),
                            "booked_by": overlapping_events[0]['summary'],
                            "event_id": overlapping_events[0]['id'],
                            "message": "There is another appointment at the specified time. Please pick another slot."
                        }
                    else:
                        logger.info(f"🔍 No overlapping appointments found for {doctor_email} at {appointment_time} on {appointment_date}")
                        # Continue to check for user conflicts since there are no time overlaps
                
            # Check if the user has existing booking on this date (Rule 2 enforcement)
            logger.info(f"🔍 Checking for existing booking for {self.from_number} on {appointment_date}")
            # Create new search params for user search with time range
            # Search in primary calendar for user's events on the specific date
            user_search_params = {
                'calendarId': doctor_email,
                'singleEvents': True,
                'orderBy': 'startTime',
                'q': self.from_number  # Search for user's phone number
            }
            # Add time range for the specific date - only look for future appointments
            if appointment_date:
                target_date = datetime.strptime(appointment_date, '%Y-%m-%d')
                # Only look for appointments from the target date onwards (future appointments)
                time_min = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                # Set timeMax to a reasonable future date (e.g., 1 day from now. can extend up to 1 years.)
                time_max = target_date.replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=1)
                user_search_params['timeMin'] = time_min.strftime('%Y-%m-%dT%H:%M:%S+05:30')
                user_search_params['timeMax'] = time_max.strftime('%Y-%m-%dT%H:%M:%S+05:30')
            
            logger.info(f"🔍 Search params for existing user: {user_search_params}")
            try:
                existing_appointments = self.service.events().list(**user_search_params).execute()
                logger.info(f"🔍 Existing appointments: {existing_appointments}")
            except Exception as api_error:
                logger.error(f"❌ Error calling Google Calendar API for existing user: {api_error}")
                logger.error(f"❌ API call params: {user_search_params}")
                raise api_error
            existing_events = existing_appointments.get('items', [])
            
            # Filter out past appointments - only consider future appointments
            current_time = datetime.now()
            future_events = []
            
            for event in existing_events:
                event_start = event.get('start', {}).get('dateTime')
                if event_start:
                    try:
                        # Parse event start time
                        if event_start.endswith('Z'):
                            event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                        else:
                            event_start_dt = datetime.fromisoformat(event_start)
                        
                        # Convert to IST for comparison
                        ist = pytz.timezone('Asia/Kolkata')
                        event_start_ist = event_start_dt.astimezone(ist).replace(tzinfo=None)
                        
                        # Only include future appointments
                        if event_start_ist > current_time:
                            future_events.append(event)
                            logger.info(f"🔍 Found future appointment: {event_start_ist.strftime('%Y-%m-%d %H:%M')}")
                        else:
                            logger.info(f"🔍 Skipping past appointment: {event_start_ist.strftime('%Y-%m-%d %H:%M')}")
                    except Exception as parse_error:
                        logger.error(f"❌ Error parsing event time: {parse_error}")
                        continue
            
            # Rule 2: Check if user has ANY existing FUTURE appointments on this date
            if future_events:
                logger.info(f"🔍 User has {len(future_events)} future booking(s) on {appointment_date}")
                return {
                    "events_found": len(future_events),
                    "booked_by": self.from_number,
                    "event_id": future_events[0]['id'],
                    "message": "User has existing booking on this date. Do you want me to reschedule the appointment ?"
                }
            else:
                logger.info(f"🔍 No future appointments found at {appointment_time} on {appointment_date}")
                return {
                    "events_found": 0,
                    "booked_by": None,
                    "event_id": None,
                    "message": "No appointment found at the specified time. Do you want me to book this slot ?"
                }
            
        except Exception as e:
            logger.info(f"❌ Error finding appointment: {e}")
            return None

    def reschedule_appointment(self, event_details: dict):
        """Reschedule an existing appointment"""
        try:
            doctor_email = event_details.get('doctor_email')
            patient_name = event_details.get('patient_name')
            old_appointment_date = event_details.get('old_appointment_date')
            new_appointment_date = event_details.get('new_appointment_date')
            new_appointment_time = event_details.get('new_appointment_time')

            # First, find the existing appointment at the old time
            data_for_find_existing = {
                "doctor_email": doctor_email,
                "appointment_date": old_appointment_date,
                "appointment_time": "00:00",  # We'll search by date only for existing appointments
                "new_appointment_date": new_appointment_date,
                "new_appointment_time": new_appointment_time
            }
            
            # Check for conflicts at the new time
            data_for_conflict_check = {
                "doctor_email": doctor_email,
                "appointment_date": new_appointment_date,
                "appointment_time": new_appointment_time,
                "new_appointment_date": new_appointment_date,
                "new_appointment_time": new_appointment_time
            }

            logger.info(f"📅 Rescheduling appointment for {patient_name} on {new_appointment_date} at {new_appointment_time}")

            # First, check for conflicts at the new time
            conflict_check = self.find_appointment(data_for_conflict_check, is_rescheduling=False)
            if conflict_check and "another appointment at the specified time" in conflict_check.get('message', ''):
                return {
                    "success": False,
                    "error": "Time conflict",
                    "message": conflict_check.get('message', 'There is a conflict with the new appointment time.')
                }
            
            # Now find the existing appointment to reschedule
            existing_appointments = self.find_appointment(data_for_find_existing, is_rescheduling=True)
            if not existing_appointments or existing_appointments.get('events_found', 0) == 0:
                logger.info(f"❌ No appointment found for {patient_name} on {old_appointment_date}")
                return {
                    "success": False,
                    "error": "Appointment not found",
                    "message": "No appointment found for the same doctor and patient on the same date."
                }
            
            # Get the event ID from the response
            event_id = existing_appointments.get('event_id')
            if not event_id:
                return {
                    "success": False,
                    "error": "No event ID",
                    "message": "Could not find the appointment to reschedule."
                }
            
            # Get the event and update it
            try:
                event = self.service.events().get(calendarId=doctor_email, eventId=event_id).execute()
                logger.info(f"🔍 Retrieved event for rescheduling: {event}")
            except Exception as api_error:
                logger.error(f"❌ Error retrieving event for rescheduling: {api_error}")
                logger.error(f"❌ Event ID: {event_id}")
                raise api_error
            
            # Calculate end time (30 minutes after start time)
            start_datetime = datetime.strptime(new_appointment_date + ' ' + new_appointment_time, '%Y-%m-%d %H:%M')
            end_datetime = start_datetime + timedelta(minutes=30)
            
            # Format for Google Calendar API (RFC3339 format with timezone)
            start_iso = start_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            end_iso = end_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            
            event['start']['dateTime'] = start_iso
            event['end']['dateTime'] = end_iso
            try:
                updated_event = self.service.events().update(calendarId=doctor_email, eventId=event_id, body=event).execute()
                logger.info(f"✅ Appointment rescheduled successfully!")
            except Exception as api_error:
                logger.error(f"❌ Error updating event: {api_error}")
                logger.error(f"❌ Event ID: {event_id}")
                logger.error(f"❌ Updated event data: {event}")
                raise api_error
            logger.info(f"Event ID: {updated_event['id']}")

            return {
                "success": True,
                "message": "Appointment rescheduled successfully!"
            }

        except Exception as e:
            logger.info(f"❌ Error rescheduling appointment: {e}")
            return None

    def cancel_appointment(self, event_details: dict):
        """Cancel an existing appointment"""
        try:
            doctor_email = event_details.get('doctor_email')
            patient_name = event_details.get('patient_name')
            appointment_date = event_details.get('appointment_date')
            appointment_time = event_details.get('appointment_time', '00:00')  # Default to 00:00 if not provided

            logger.info(f"📅 Cancelling appointment for {patient_name} on {appointment_date}")

            # Create a proper event_details dict for find_appointment
            # If no specific time is provided, search by date only to find any appointment by the user
            if appointment_time == '00:00':
                # Search for any appointment by the user on this date
                find_details = {
                    'doctor_email': doctor_email,
                    'patient_name': patient_name,
                    'appointment_date': appointment_date,
                    'appointment_time': '00:00'  # This will trigger the user search logic
                }
            else:
                # Search for specific time slot
                find_details = {
                    'doctor_email': doctor_email,
                    'patient_name': patient_name,
                    'appointment_date': appointment_date,
                    'appointment_time': appointment_time
                }
            
            existing_appointments = self.find_appointment(find_details)
            if not existing_appointments or existing_appointments.get('events_found', 0) == 0:
                logger.info(f"❌ No appointment found for {patient_name} on {appointment_date}")
                return {
                    "success": False,
                    "error": "Appointment not found",
                    "message": "No appointment found for the same doctor and patient on the same date."
                }

            # Get the event ID from the response
            event_id = existing_appointments.get('event_id')
            if not event_id:
                return {
                    "success": False,
                    "error": "No event ID",
                    "message": "Could not find the appointment to cancel."
                }

            # Delete the appointment
            try:
                self.service.events().delete(calendarId=doctor_email, eventId=event_id).execute()
                logger.info(f"✅ Appointment cancelled successfully!")
            except Exception as api_error:
                logger.error(f"❌ Error deleting event: {api_error}")
                logger.error(f"❌ Event ID: {event_id}")
                raise api_error
            logger.info(f"Event ID: {event_id}")

            return {
                "success": True,
                "message": "Appointment cancelled successfully!"
            }

        except Exception as e:
            logger.info(f"❌ Error cancelling appointment: {e}")
            return None


    def get_oauth_token_from_db(self):
        """Get the OAuth token for AI agent ID 7232d36a-32b0-4d6c-9abd-446635299237 from the database"""
        logger.info(f"🔍 Getting OAuth token from DB for agent_id: {self.agent_id}, tool_id: {self.tool_id}")
        
        try:
            with next(get_session()) as db:
                
                # Find the AI agent tool record for the specific AI agent ID
                # Agent Id: 7232d36a-32b0-4d6c-9abd-446635299237
                # Tool Id: 3c6f5b58-d097-47dd-bdb1-39e55ff3faf6
                ai_agent_id = self.agent_id
                tool_id = self.tool_id
                
                ai_agent_tool = db.exec(
                    select(AIAgentTool)
                    .where(
                        AIAgentTool.tool_id == tool_id,
                        AIAgentTool.ai_agent_id == ai_agent_id
                    )
                ).first()
                
                if not ai_agent_tool:
                    logger.info(f"❌ AI agent tool record not found for AI agent ID: {ai_agent_id}")
                    return None
                
                if not ai_agent_tool.oauth_token:
                    logger.info(f"❌ No OAuth token found for AI agent ID: {ai_agent_id}")
                    return None
                
                logger.info(f"✅ Found OAuth token for AI agent ID: {ai_agent_id}")
                if ai_agent_tool.email_id:
                    logger.info(f"   Associated email: {ai_agent_tool.email_id}")
                return ai_agent_tool.oauth_token
                
        except Exception as e:
            logger.error(f"❌ Error getting OAuth token from DB: {e}")
            return None

    def get_google_oauth_config(self):
        """Get Google OAuth configuration from the credentials file"""
        try:
            # Get the project root directory (3 levels up from calendar_service.py)
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'google-calendar-credentials.json')
            logger.info(f"🔍 Reading OAuth config from: {config_path}")
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            web_config = config.get('web', {})
            logger.info(f"🔍 OAuth config loaded, client_id: {web_config.get('client_id', 'None')[:20]}...")
            
            return {
                'client_id': web_config.get('client_id'),
                'client_secret': web_config.get('client_secret'),
                'token_uri': web_config.get('token_uri', 'https://oauth2.googleapis.com/token')
            }
        except Exception as e:
            logger.error(f"❌ Error reading Google OAuth config: {e}")
            return None

    def update_oauth_token_in_db(self, ai_agent_id, tool_id, new_token_data):
        """Update the OAuth token in the database with refreshed token data"""
        logger.info(f"🔄 Updating OAuth token in DB for agent_id: {ai_agent_id}, tool_id: {tool_id}")
        try:
            with next(get_session()) as db:
                # Find the AI agent tool record
                ai_agent_tool = db.exec(
                    select(AIAgentTool)
                    .where(
                        AIAgentTool.tool_id == tool_id,
                        AIAgentTool.ai_agent_id == ai_agent_id
                    )
                ).first()
                
                if not ai_agent_tool:
                    logger.info(f"❌ AI agent tool record not found for AI agent ID: {ai_agent_id}")
                    return False
                
                # Update the OAuth token
                ai_agent_tool.oauth_token = new_token_data
                db.add(ai_agent_tool)
                db.commit()
                
                logger.info(f"✅ OAuth token updated in database for AI agent ID: {ai_agent_id}")
                return True
                
        except Exception as e:
            logger.info(f"❌ Error updating OAuth token in database: {e}")
            return False

    def clear_invalid_oauth_token(self):
        """Clear the invalid OAuth token from database to prevent future failed attempts"""
        logger.info(f"🗑️ Clearing invalid OAuth token for agent_id: {self.agent_id}, tool_id: {self.tool_id}")
        try:
            with next(get_session()) as db:
                # Find the AI agent tool record
                ai_agent_tool = db.exec(
                    select(AIAgentTool)
                    .where(
                        AIAgentTool.tool_id == self.tool_id,
                        AIAgentTool.ai_agent_id == self.agent_id
                    )
                ).first()
                
                if ai_agent_tool:
                    # Clear the OAuth token
                    ai_agent_tool.oauth_token = None
                    db.add(ai_agent_tool)
                    db.commit()
                    logger.info(f"✅ Invalid OAuth token cleared from database for AI agent ID: {self.agent_id}")
                    return True
                else:
                    logger.error(f"❌ AI agent tool record not found for AI agent ID: {self.agent_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error clearing OAuth token from database: {e}")
            return False

    def get_credentials(self):
        """Get and refresh Google credentials"""
        logger.info(f"🔐 Getting credentials for agent_id: {self.agent_id}, tool_id: {self.tool_id}")
        
        # Get OAuth token from database
        oauth_token_data = self.get_oauth_token_from_db()
        if not oauth_token_data:
            logger.error("❌ Failed to get OAuth token from database")
            return None
        
        logger.info(f"🔐 OAuth token data retrieved: {oauth_token_data.get('access_token', 'None')[:20]}...")
        
        # Get Google OAuth configuration
        oauth_config = self.get_google_oauth_config()
        if not oauth_config:
            logger.error("❌ Failed to get Google OAuth configuration")
            return None
        
        logger.info(f"🔐 OAuth config retrieved: client_id={oauth_config.get('client_id', 'None')[:20]}...")
        
        # Store the original token data for comparison
        original_token = oauth_token_data.get('access_token')
        
        # Create credentials from the OAuth token and config
        try:
            logger.info(f"🔐 Creating credentials with scopes: {SCOPES}")
            credentials = Credentials(
                token=oauth_token_data.get('access_token'),
                refresh_token=oauth_token_data.get('refresh_token'),
                token_uri=oauth_config['token_uri'],
                client_id=oauth_config['client_id'],
                client_secret=oauth_config['client_secret'],
                scopes=SCOPES
            )
            logger.info(f"🔐 Credentials created successfully, expired: {credentials.expired}")
        
            # Refresh the token if needed
            if credentials.expired and credentials.refresh_token:
                logger.info(f"🔄 Token expired, attempting refresh...")
                try:
                    credentials.refresh(Request())
                    logger.info("✅ OAuth token refreshed successfully")
                except Exception as refresh_error:
                    logger.error(f"❌ Failed to refresh OAuth token: {refresh_error}")
                    # Check if it's an invalid_grant error (refresh token expired/revoked)
                    if "invalid_grant" in str(refresh_error):
                        logger.error("🔄 Refresh token has expired or been revoked. Re-authentication required.")
                        # Clear the invalid token from database to prevent future attempts
                        self.clear_invalid_oauth_token()
                        return None
                    else:
                        # Re-raise other errors
                        raise refresh_error
                
                # Check if the token was actually refreshed (changed)
                if credentials.token != original_token:
                    print("🔄 Token was refreshed, updating database...")
                    
                    # Prepare new token data
                    new_token_data = {
                        'access_token': credentials.token,
                        'refresh_token': credentials.refresh_token,
                        'token_uri': credentials.token_uri,
                        'client_id': credentials.client_id,
                        'client_secret': credentials.client_secret,
                        'scopes': credentials.scopes,
                        'expiry': credentials.expiry.isoformat() if credentials.expiry else None
                    }
                    
                    # Update the token in the database
                    # ai_agent_id = uuid.UUID("7232d36a-32b0-4d6c-9abd-446635299237")
                    # tool_id = uuid.UUID("3c6f5b58-d097-47dd-bdb1-39e55ff3faf6")
                    ai_agent_id = self.agent_id
                    tool_id = self.tool_id
                    
                    update_success = self.update_oauth_token_in_db(ai_agent_id, tool_id, new_token_data)
                    if update_success:
                        print("✅ Refreshed token saved to database")
                    else:
                        print("⚠️  Failed to save refreshed token to database")
        
            logger.info(f"🔐 Returning credentials successfully")
            return credentials
        
        except Exception as e:
            logger.error(f"❌ Error creating credentials: {e}")
            return None

    def check_available_slots(self, doctor_email: str, date: str):
        """Check available appointment slots for a doctor on a specific date"""
        try:
            logger.info(f"📅 Checking available slots for {doctor_email} on {date}")
            
            # Parse the input date
            if len(date) == 10:  # YYYY-MM-DD format
                date_obj = datetime.strptime(date, '%Y-%m-%d')
            else:
                # Try to parse as ISO format
                date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
            
            # Set timezone to IST
            ist_tz = pytz.timezone('Asia/Kolkata')
            date_obj = ist_tz.localize(date_obj)
            
            # Define working hours (9 AM to 5 PM IST)
            start_hour = 9
            end_hour = 17
            slot_duration_minutes = 30
            
            # Create start and end times for the day
            day_start = date_obj.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            day_end = date_obj.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            
            # Query existing events for the day, filtering by doctor email
            search_params = {
                'calendarId': 'primary',
                'timeMin': day_start.isoformat(),
                'timeMax': day_end.isoformat(),
                'singleEvents': True,
                'orderBy': 'startTime',
                'q': f'"{doctor_email}"'  # Search for events containing the doctor's email
            }
            
            logger.info(f"🔍 Search params for available slots: {search_params}")
            
            try:
                events_result = self.service.events().list(**search_params).execute()
                logger.info(f"🔍 Available slots API response: {events_result}")
            except Exception as api_error:
                logger.error(f"❌ Error calling Google Calendar API for available slots: {api_error}")
                logger.error(f"❌ API call params: {search_params}")
                raise api_error
                
            events = events_result.get('items', [])
            
            # Additional filtering to ensure events are specifically for this doctor
            doctor_events = []
            for event in events:
                # Check if doctor email is in attendees, description, or summary
                is_doctor_event = False
                
                # Check attendees
                if 'attendees' in event:
                    for attendee in event['attendees']:
                        if attendee.get('email', '').lower() == doctor_email.lower():
                            is_doctor_event = True
                            break
                
                # Check description
                if not is_doctor_event and 'description' in event:
                    if doctor_email.lower() in event['description'].lower():
                        is_doctor_event = True
                
                # Check summary
                if not is_doctor_event and 'summary' in event:
                    if doctor_email.lower() in event['summary'].lower():
                        is_doctor_event = True
                
                if is_doctor_event:
                    doctor_events.append(event)
                    logger.info(f"📅 Doctor Event: {event.get('summary', 'No title')}")
                    logger.info(f"   Start: {event['start']}")
                    logger.info(f"   End: {event['end']}")
                    logger.info(f"   Attendees: {[a.get('email') for a in event.get('attendees', [])]}")
                    logger.info(f"   Description: {event.get('description', 'No description')}")
                    logger.info(f"   ---")
            
            logger.info(f"📋 Found {len(doctor_events)} doctor-specific events for {date}")
            
            # Convert events to time ranges
            booked_ranges = []
            for event in doctor_events:
                start_time = event['start'].get('dateTime', event['start'].get('date'))
                end_time = event['end'].get('dateTime', event['end'].get('date'))
                
                # Parse event times
                if 'T' in start_time:
                    event_start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    event_end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    
                    # Convert to IST if needed
                    if event_start.tzinfo is None:
                        event_start = ist_tz.localize(event_start)
                    if event_end.tzinfo is None:
                        event_end = ist_tz.localize(event_end)
                    
                    booked_ranges.append((event_start, event_end))
            
            # Generate all possible slots
            all_slots = []
            current_time = day_start
            
            while current_time < day_end:
                slot_end = current_time + timedelta(minutes=slot_duration_minutes)
                if slot_end <= day_end:
                    all_slots.append((current_time, slot_end))
                current_time += timedelta(minutes=slot_duration_minutes)
            
            # Filter out booked slots
            available_slots = []
            for slot_start, slot_end in all_slots:
                is_available = True
                
                for booked_start, booked_end in booked_ranges:
                    # Check for overlap
                    if (slot_start < booked_end and slot_end > booked_start):
                        is_available = False
                        break
                
                if is_available:
                    # Format time for display
                    start_time_str = slot_start.strftime('%H:%M')
                    end_time_str = slot_end.strftime('%H:%M')
                    available_slots.append({
                        'start_time': start_time_str,
                        'end_time': end_time_str,
                        'start_datetime': slot_start.isoformat(),
                        'end_datetime': slot_end.isoformat()
                    })
            
            logger.info(f"✅ Found {len(available_slots)} available slots for {date}")
            
            # Format response
            if available_slots:
                slot_list = [f"{slot['start_time']} - {slot['end_time']}" for slot in available_slots]
                return {
                    "success": True,
                    "available_slots": slot_list,
                    "date": date,
                    "doctor_email": doctor_email,
                    "message": f"Found {len(available_slots)} available slots for {date}",
                    "detailed_slots": available_slots
                }
            else:
                return {
                    "success": False,
                    "available_slots": [],
                    "date": date,
                    "doctor_email": doctor_email,
                    "message": f"No available slots found for {date}"
                }
                
        except Exception as e:
            logger.info(f"❌ Error checking available slots: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to check available slots"
            }

