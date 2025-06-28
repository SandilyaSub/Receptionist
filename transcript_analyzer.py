import os
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
import google.generativeai as genai

# Configure the Gemini API key
# Make sure to set the GOOGLE_API_KEY environment variable
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

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

async def analyze_transcript(transcript: str, tenant: str) -> Optional[dict]:
    """Analyzes a transcript to extract structured data using Gemini."""
    if not transcript:
        print("Analyzer: Transcript is empty, skipping analysis.")
        return None

    schema = TENANT_SCHEMAS.get(tenant)
    if not schema:
        print(f"Analyzer: No schema found for tenant '{tenant}', skipping analysis.")
        return None

    prompt = load_analyzer_prompt(tenant, transcript)
    
    print(f"Analyzer: Analyzing transcript for tenant '{tenant}'...")

    try:
        client = genai.GenerativeModel(model_name="gemini-1.5-flash")
        response = await client.generate_content_async(
            contents=prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=schema,
            )
        )
        
        # The API returns a pydantic model instance in the `candidates[0].content.parts[0].function_call`
        # but the text representation is also directly available and parsed.
        # For simplicity, we can work with the text if it's valid JSON.
        if response.text:
            # The response.parsed is a Pydantic model instance
            model_instance = response.parsed
            # Convert the Pydantic model to a dictionary for JSONB storage
            return model_instance.dict()
        else:
            print("Analyzer: Received an empty response from Gemini.")
            return None

    except Exception as e:
        print(f"Analyzer: An error occurred during transcript analysis: {e}")
        return None
