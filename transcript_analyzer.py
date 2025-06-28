import os
import logging
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from google import genai

# Get a logger instance
logger = logging.getLogger(__name__)

# The API client is configured within the analyze_transcript function.

# Define the possible types for a call
CallType = Literal["Booking", "Status Check", "Cancellation", "Informational", "Others"]

class BakeryCallDetails(BaseModel):
    """Structured details for a bakery call."""
    call_type: CallType = Field(description="The primary purpose of the call.")
    booking_confirmed: Optional[bool] = Field(description="Was a booking explicitly confirmed?", default=None)
    customer_name: Optional[str] = Field(description="The name of the customer.", default=None)
    phone_number: Optional[str] = Field(description="The customer's phone number.", default=None)
    weight_of_cake: Optional[str] = Field(description="The weight of the cake (e.g., '1kg', '500g').", default=None)
    egg_or_eggless: Optional[Literal["Egg", "Eggless"]] = Field(description="Whether the cake should have eggs or be eggless.", default=None)
    flavour_name: Optional[str] = Field(description="The flavor of the cake.", default=None)
    shape_of_the_cake: Optional[str] = Field(description="The shape of the cake.", default=None)
    message_on_cake: Optional[str] = Field(description="A message to be written on the cake.", default=None)
    custom_additions: Optional[str] = Field(description="Any other custom additions or special requests.", default=None)
    pickup_time: Optional[str] = Field(description="The requested time for pickup.", default=None)
    price: Optional[float] = Field(description="The price of the items discussed.", default=None)
    gst: Optional[float] = Field(description="The Goods and Services Tax amount.", default=None)
    total_price: Optional[float] = Field(description="The total price including all taxes.", default=None)

class SaloonCallDetails(BaseModel):
    """Structured details for a saloon call."""
    call_type: CallType = Field(description="The primary purpose of the call.")
    booking_confirmed: Optional[bool] = Field(description="Was a booking explicitly confirmed?", default=None)
    customer_name: Optional[str] = Field(description="The name of the customer.", default=None)
    phone_number: Optional[str] = Field(description="The customer's phone number.", default=None)
    stylist_name: Optional[str] = Field(description="The name of the requested stylist.", default=None)
    service_name: Optional[str] = Field(description="The name of the service requested (e.g., 'haircut', 'manicure').", default=None)
    booking_time_slot: Optional[str] = Field(description="The requested time slot for the booking.", default=None)
    customizations: Optional[str] = Field(description="Any other customizations or special requests.", default=None)
    price: Optional[float] = Field(description="The price of the service.", default=None)
    gst: Optional[float] = Field(description="The Goods and Services Tax amount.", default=None)
    total_price: Optional[float] = Field(description="The total price including all taxes.", default=None)

# A dictionary to map tenants to their respective Pydantic models
TENANT_SCHEMAS = {
    "bakery": BakeryCallDetails,
    "saloon": SaloonCallDetails,
}

def load_analyzer_prompt(tenant: str, transcript: str) -> str:
    """Loads the analyzer prompt for a given tenant and injects the transcript."""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', f'prompt-{tenant}-analyzer.txt')
        with open(prompt_path, 'r') as f:
            prompt_template = f.read()
        return prompt_template.format(transcript=transcript)
    except FileNotFoundError:
        # Fallback to a generic prompt if a tenant-specific one isn't found
        return f"""Analyze the following transcript and extract key details. Classify the call's purpose and extract any relevant information mentioned.

Transcript:
---
{transcript}
---
"""

async def analyze_transcript(transcript: str, tenant: str, api_key: str) -> Optional[dict]:
    """Analyzes a transcript to extract structured data using Gemini."""
    if not transcript:
        logger.warning("Analyzer: Transcript is empty, skipping analysis.")
        return None

    schema = TENANT_SCHEMAS.get(tenant)
    if not schema:
        logger.error(f"Analyzer: No schema found for tenant '{tenant}', skipping analysis.")
        return None

    prompt = load_analyzer_prompt(tenant, transcript)
    
    logger.info(f"Analyzer: Analyzing transcript for tenant '{tenant}' using schema {schema.__name__}.")
    logger.debug(f"Analyzer: Prompt sent to Gemini: {prompt[:500]}...")

    try:
        # Use the client pattern as specified by the user
        client = genai.Client(api_key=api_key)
        response = await client.models.generate_content_async(
            model="gemini-1.5-flash", # Corrected model parameter name
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        
        logger.debug(f"Analyzer: Raw Gemini response text: {response.text}")

        # The response.parsed attribute directly contains the instantiated Pydantic object
        if response.parsed:
            model_instance = response.parsed
            logger.info(f"Analyzer: Successfully parsed response. Call type: {model_instance.call_type}")
            # Convert the Pydantic model to a dictionary for JSONB storage
            return model_instance.dict()
        else:
            logger.warning("Analyzer: Gemini response was not parsable into the schema. `response.parsed` is empty.")
            return None

    except Exception as e:
        logger.error(f"Analyzer: An error occurred during transcript analysis: {e}", exc_info=True)
        return None
