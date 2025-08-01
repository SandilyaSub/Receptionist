"""
Business Data Schema for Prompt Generation

Defines the structure of business data collected during onboarding
that will be used to generate AI agent prompts.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

class BusinessType(Enum):
    HEALTHCARE = "healthcare"
    FOOD_BEVERAGE = "food_beverage"
    RETAIL = "retail"
    SERVICES = "services"
    EDUCATION = "education"
    HOSPITALITY = "hospitality"
    BEAUTY_WELLNESS = "beauty_wellness"
    AUTOMOTIVE = "automotive"
    REAL_ESTATE = "real_estate"
    TECHNOLOGY = "technology"
    OTHER = "other"

class LanguageCode(Enum):
    ENGLISH = "en"
    HINDI = "hi"
    TELUGU = "te"
    TAMIL = "ta"
    KANNADA = "kn"
    MALAYALAM = "ml"
    MARATHI = "mr"
    GUJARATI = "gu"
    BENGALI = "bn"
    PUNJABI = "pa"

@dataclass
class BusinessData:
    """Complete business information for prompt generation."""
    
    # Basic Information
    business_name: str
    business_type: BusinessType
    location: str
    
    # Contact & Operations
    phone_number: str
    working_hours: str
    
    # Services & Products
    services: List[str]
    
    # Language & Communication
    primary_language: LanguageCode
    supported_languages: List[LanguageCode]
    
    # Optional fields with defaults
    website: Optional[str] = None
    products: Optional[List[str]] = None
    pricing_info: Optional[Dict[str, Any]] = None
    
    # Business-Specific Details
    welcome_message: Optional[str] = None
    business_description: str = ""
    special_instructions: Optional[str] = None
    
    # Operational Constraints
    appointment_required: bool = False
    online_booking_available: bool = False
    payment_methods: Optional[List[str]] = None
    delivery_available: bool = False
    
    # Custom Fields (from onboarding form)
    custom_fields: Optional[Dict[str, Any]] = None

@dataclass
class GeneratedPrompt:
    """Structure for the generated prompt output."""
    
    prompt_text: str
    business_data: BusinessData
    generation_timestamp: str
    quality_score: Optional[float] = None
    validation_notes: Optional[List[str]] = None
    
    def save_to_file(self, filepath: str) -> None:
        """Save the generated prompt to a file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.prompt_text)

# Example business data (matching the onboarding form screenshot)
EXAMPLE_BUSINESS_DATA = BusinessData(
    business_name="Sreedevi Dental Clinic",
    business_type=BusinessType.HEALTHCARE,
    location="Rajahmundry",
    phone_number="+91-9876543210",
    working_hours="9:00 AM - 6:00 PM, Monday to Saturday",
    business_description="Premier dental care clinic providing comprehensive oral health services",
    services=[
        "General dental consultation",
        "Teeth cleaning and scaling",
        "Root canal treatment",
        "Dental fillings",
        "Tooth extraction",
        "Dental crowns and bridges",
        "Orthodontic treatment",
        "Dental implants"
    ],
    primary_language=LanguageCode.TELUGU,
    supported_languages=[LanguageCode.TELUGU, LanguageCode.ENGLISH, LanguageCode.HINDI],
    appointment_required=True,
    online_booking_available=False,
    welcome_message="Welcome to Sreedevi Dental Clinic. We provide quality dental care with modern equipment.",
    special_instructions="Always ask about dental history and current pain levels. Emphasize appointment booking."
)
