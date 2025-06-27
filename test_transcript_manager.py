#!/usr/bin/env python3
"""
Test script for TranscriptManager functionality.
This script tests the TranscriptManager class from new_exotel_bridge.py in isolation.
"""

import os
import sys
import json
import uuid
from datetime import datetime

# Import the TranscriptManager class from new_exotel_bridge.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from new_exotel_bridge import TranscriptManager

def test_transcript_manager():
    """Test the TranscriptManager class functionality."""
    print("Testing TranscriptManager functionality...")
    
    # Generate a unique call SID for this test
    call_sid = f"test-{uuid.uuid4()}"
    print(f"Using test call SID: {call_sid}")
    
    # Create a TranscriptManager instance
    transcript_manager = TranscriptManager(call_sid=call_sid)
    print("Created TranscriptManager instance")
    
    # Simulate a conversation
    print("Simulating a conversation...")
    
    # User turn 1
    transcript_manager.add_user_transcript("Hello, I'd like to order a cake.")
    print("Added user transcript 1")
    
    # Model turn 1
    transcript_manager.add_model_transcript("Hi there! I'd be happy to help you order a cake. ")
    transcript_manager.add_model_transcript("What type of cake are you interested in?")
    print("Added model transcript 1")
    
    # User turn 2
    transcript_manager.add_user_transcript("I want a chocolate cake for my birthday.")
    print("Added user transcript 2")
    
    # Model turn 2
    transcript_manager.add_model_transcript("Great choice! ")
    transcript_manager.add_model_transcript("Our chocolate cake is very popular. ")
    transcript_manager.add_model_transcript("What size would you like?")
    print("Added model transcript 2")
    
    # User turn 3
    transcript_manager.add_user_transcript("A medium size cake, please.")
    print("Added user transcript 3")
    
    # Model turn 3
    transcript_manager.add_model_transcript("Perfect! ")
    transcript_manager.add_model_transcript("I've noted down a medium chocolate cake for your birthday. ")
    transcript_manager.add_model_transcript("When would you like to pick it up?")
    print("Added model transcript 3")
    
    # Save the transcript
    transcript_manager.save_transcript()
    print("Saved transcript")
    
    # Verify the transcript file exists
    transcript_file = os.path.join("call_details", f"{call_sid}.json")
    if os.path.exists(transcript_file):
        print(f"SUCCESS: Transcript file created at {transcript_file}")
        
        # Read and display the transcript
        with open(transcript_file, 'r') as f:
            transcript_data = json.load(f)
            print("\nTranscript content:")
            print(json.dumps(transcript_data, indent=2))
            
        return True
    else:
        print(f"ERROR: Transcript file not found at {transcript_file}")
        return False

if __name__ == "__main__":
    success = test_transcript_manager()
    if success:
        print("\nTranscript Manager test completed successfully!")
        sys.exit(0)
    else:
        print("\nTranscript Manager test failed!")
        sys.exit(1)
