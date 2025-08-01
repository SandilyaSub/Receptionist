"""
Call Timeout Manager for AI Voice Agent

Handles inactivity timeouts (>2 minutes) and maximum call duration (>10 minutes)
with language-matched exit statements.
"""

import time
import asyncio
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class CallTimeoutManager:
    """Manages call timeouts for inactivity and maximum duration."""
    
    def __init__(self):
        # Configuration
        self.max_inactivity_threshold = 120  # 2 minutes in seconds
        self.max_call_duration = 600  # 10 minutes in seconds
        
        # State tracking
        self.call_start_time = time.time()
        self.last_user_input_time = time.time()
        self.detected_language = "english"  # Default
        self.is_terminated = False
        
        # Background tasks
        self.inactivity_task = None
        self.duration_task = None
        
        logger.info(f"CallTimeoutManager initialized - max_inactivity: {self.max_inactivity_threshold}s, max_duration: {self.max_call_duration}s")
    
    def update_user_activity(self):
        """Call this whenever user provides input."""
        self.last_user_input_time = time.time()
        logger.debug("User activity updated")
    
    def set_detected_language(self, language: str):
        """Update the detected conversation language."""
        if language and language.lower() in ["english", "hindi", "telugu"]:
            self.detected_language = language.lower()
            logger.debug(f"Language updated to: {self.detected_language}")
    
    def reset_timers(self):
        """Reset all timers to current time. Call this when the call officially starts."""
        current_time = time.time()
        self.call_start_time = current_time
        self.last_user_input_time = current_time
        logger.info("All timeout timers reset to current time")
    
    def get_inactivity_duration(self) -> float:
        """Get current inactivity duration in seconds."""
        return time.time() - self.last_user_input_time
    
    def get_call_duration(self) -> float:
        """Get total call duration in seconds."""
        return time.time() - self.call_start_time
    
    def should_terminate_for_inactivity(self) -> bool:
        """Check if call should be terminated due to inactivity."""
        return self.get_inactivity_duration() > self.max_inactivity_threshold
    
    def should_terminate_for_duration(self) -> bool:
        """Check if call should be terminated due to max duration."""
        return self.get_call_duration() > self.max_call_duration
    
    def get_status(self) -> Dict:
        """Get current timeout status for debugging."""
        return {
            "call_duration": self.get_call_duration(),
            "inactivity_duration": self.get_inactivity_duration(),
            "detected_language": self.detected_language,
            "is_terminated": self.is_terminated,
            "should_terminate_inactivity": self.should_terminate_for_inactivity(),
            "should_terminate_duration": self.should_terminate_for_duration()
        }


class CallTerminationMessages:
    """Manages termination messages in different languages."""
    
    # Inactivity timeout messages
    INACTIVITY_MESSAGES = {
        "english": "We haven't detected any activity on the call for over two minutes. The call will now be disconnected. Thank you for calling.",
        
        "hindi": "कॉल पर दो मिनट से अधिक समय से कोई गतिविधि नहीं हुई है। अब कॉल को डिस्कनेक्ट कर दिया जाएगा। कॉल करने के लिए धन्यवाद।",
        
        "telugu": "రెండు నిమిషాలకు పైగా కాల్‌లో ఎలాంటి స్పందన లేదు. కాల్ ఇప్పుడు డిస్‌కనెక్ట్ అవుతుంది. కాల్ చేసినందుకు ధన్యవాదాలు.",
        
        "default": "We haven't detected any activity on the call for over two minutes. The call will now be disconnected. Thank you for calling."
    }
    
    # Maximum duration messages
    DURATION_MESSAGES = {
        "english": "Sorry, maximum call duration of 10 minutes exceeded, will need to cut the call. Thank you for your time.",
        
        "hindi": "क्षमा करें, अधिकतम कॉल अवधि 10 मिनट पूरी हो गई है, कॉल काटनी होगी। आपके समय के लिए धन्यवाद।",
        
        "telugu": "క్షమించండి, గరిష్ట కాల్ వ్యవధి 10 నిమిషాలు మించిపోయింది, కాల్‌ను కట్ చేయాల్సి వస్తోంది. మీ సమయానికి ధన్యవాదాలు.",
        
        "default": "Sorry, maximum call duration of 10 minutes exceeded, will need to cut the call. Thank you for your time."
    }
    
    @staticmethod
    def get_inactivity_message(language: str) -> str:
        """Get inactivity termination message in specified language."""
        return CallTerminationMessages.INACTIVITY_MESSAGES.get(
            language.lower(), 
            CallTerminationMessages.INACTIVITY_MESSAGES["default"]
        )
    
    @staticmethod
    def get_duration_message(language: str) -> str:
        """Get duration termination message in specified language."""
        return CallTerminationMessages.DURATION_MESSAGES.get(
            language.lower(), 
            CallTerminationMessages.DURATION_MESSAGES["default"]
        )
    
    @staticmethod
    def get_all_messages() -> Dict:
        """Get all termination messages for debugging."""
        return {
            "inactivity": CallTerminationMessages.INACTIVITY_MESSAGES,
            "duration": CallTerminationMessages.DURATION_MESSAGES
        }


def detect_language_from_text(text: str) -> Optional[str]:
    """Simple language detection based on common words/patterns."""
    if not text:
        return None
        
    text_lower = text.lower()
    
    # Telugu indicators (using common Telugu words)
    telugu_patterns = ["నమస్కారం", "ధన్యవాదాలు", "మీరు", "నేను", "ఎలా", "ఏమి", "కాల్", "స్పందన"]
    if any(pattern in text for pattern in telugu_patterns):
        return "telugu"
    
    # Hindi indicators (using common Hindi words)
    hindi_patterns = ["नमस्ते", "धन्यवाद", "आप", "मैं", "कैसे", "क्या", "कॉल", "गतिविधि"]
    if any(pattern in text for pattern in hindi_patterns):
        return "hindi"
    
    # Default to English for any other text
    return "english"


# Gemini Function Definition for call termination
CALL_TERMINATION_FUNCTION = {
    "name": "initiate_call_termination",
    "description": "Initiate call termination due to timeout conditions (inactivity or max duration)",
    "parameters": {
        "type": "object",
        "properties": {
            "termination_reason": {
                "type": "string",
                "enum": ["inactivity_timeout", "duration_exceeded"],
                "description": "Reason for call termination"
            },
            "current_language": {
                "type": "string",
                "enum": ["english", "hindi", "telugu"],
                "description": "Current conversation language for exit message"
            },
            "should_terminate_immediately": {
                "type": "boolean",
                "description": "Whether to terminate the call immediately after speaking the exit message"
            }
        },
        "required": ["termination_reason", "current_language", "should_terminate_immediately"]
    }
}


# Configuration constants
class CallTimeoutConfig:
    MAX_INACTIVITY_THRESHOLD = 120  # 2 minutes
    MAX_CALL_DURATION = 600  # 10 minutes
    
    # Monitoring intervals
    INACTIVITY_CHECK_INTERVAL = 10  # seconds
    DURATION_CHECK_INTERVAL = 30   # seconds
    
    # Grace period for exit message
    EXIT_MESSAGE_GRACE_PERIOD = 3  # seconds


if __name__ == "__main__":
    # Test the timeout manager
    print("Testing CallTimeoutManager...")
    
    manager = CallTimeoutManager()
    messages = CallTerminationMessages()
    
    print(f"Initial status: {manager.get_status()}")
    
    # Test language detection
    test_texts = [
        "Hello, how are you?",
        "नमस्ते, आप कैसे हैं?",
        "నమస్కారం, మీరు ఎలా ఉన్నారు?",
        ""
    ]
    
    for text in test_texts:
        lang = detect_language_from_text(text)
        print(f"Text: '{text}' -> Language: {lang}")
    
    # Test messages
    for lang in ["english", "hindi", "telugu"]:
        print(f"\nInactivity message ({lang}): {messages.get_inactivity_message(lang)}")
        print(f"Duration message ({lang}): {messages.get_duration_message(lang)}")
