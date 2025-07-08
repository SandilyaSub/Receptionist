import os
import asyncio
import logging
import json
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types
from supabase import create_client, Client

# Configure logging
logger = logging.getLogger(__name__)

# --- Supabase Helper ---
def get_supabase_client() -> Optional[Client]:
    """Initializes and returns a sync Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_API_KEY")
    if not url or not key:
        logger.error("Supabase URL or API key not found in environment variables.")
        return None
    return create_client(url, key)

async def fetch_call_type_schema(tenant_id: str, supabase: Client) -> Optional[List[str]]:
    """Fetches the allowed call types for a given tenant from Supabase."""
    try:
        # Run the synchronous Supabase call in a separate thread
        response = await asyncio.to_thread(
            supabase.table("tenant_configs")
            .select("call_type_schema")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .single()
            .execute
        )
        
        if response.data and "call_type_schema" in response.data:
            schema = response.data["call_type_schema"]
            if "enum" in schema:
                logger.info(f"Successfully fetched call type schema for tenant '{tenant_id}'.")
                return schema["enum"]
        
        logger.error(f"No active call type schema found for tenant '{tenant_id}'.")
        # Default call types as fallback
        return ["Booking", "Status Check", "Cancellation", "Informational", "Others"]
    
    except Exception as e:
        logger.error(f"Error fetching call types for tenant '{tenant_id}' from Supabase: {e}")
        # Default call types as fallback
        return ["Booking", "Status Check", "Cancellation", "Informational", "Others"]

def create_universal_prompt(transcript: str, call_types: list) -> str:
    """Create a universal prompt for transcript analysis with the provided call types."""
    
    call_types_str = '", "'.join(call_types)
    
    return f"""You are a highly efficient data analysis assistant. You are an expert data extraction agent. Analyze the following call transcript and extract the key details. Your response MUST be a single, valid JSON object. Do not include any explanatory text, markdown formatting, or anything else outside of the JSON object.

Analyze the following call transcript between an AI receptionist and a customer.

TASK:
1. Determine the call type from these options: "{call_types_str}"
2. Extract key information from the conversation
3. Create a concise summary of what was discussed

TRANSCRIPT:
{transcript}

Respond ONLY with a JSON object in this exact format:
{{
  "call_type": "one of the call types listed above",
  "summary": "a 1-2 sentence summary of the call",
  "key_details": {{
    // Key-value pairs of important information extracted from the call
    // Examples for different call types:
    // - Booking: date, time, product/service details, customer preferences
    // - Status Check: order reference, current status
    // - Cancellation: reason, booking reference
    // Use your judgment to extract relevant details based on the call content
  }}
}}
"""

# --- Main Analyzer Function ---
async def analyze_transcript(transcript: str, tenant: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Analyzes a transcript to extract call type and key details."""
    if not transcript:
        logger.warning("Analyzer: Transcript is empty, skipping analysis.")
        return None

    supabase = get_supabase_client()
    if not supabase:
        return None

    # Fetch allowed call types for this tenant
    call_types = await fetch_call_type_schema(tenant, supabase)
    
    # Create the universal prompt
    prompt = create_universal_prompt(transcript, call_types)
    
    logger.info(f"Analyzer: Analyzing transcript for tenant '{tenant}'.")
    logger.debug(f"Analyzer: Prompt sent to Gemini: {prompt[:500]}...")

    try:
        client = genai.Client(api_key=api_key)
        
        # Call the Gemini model with the prompt
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,  # Lower temperature for more consistent output
                thinking_config=types.ThinkingConfig(
                    thinking_budget=0,
                ),
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_LOW_AND_ABOVE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_LOW_AND_ABOVE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_LOW_AND_ABOVE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_LOW_AND_ABOVE",
                    ),
                ],
                response_mime_type="application/json",
                system_instruction=[
                    types.Part.from_text(text="""You are a highly efficient data analysis assistant specializing in call transcript analysis. Your task is to extract the key information from transcripts and provide it in a structured JSON format. Be precise, accurate, and thorough in your extraction. Ensure all JSON you output is valid and follows the exact requested format."""),
                ],
            )
        )
        
        logger.debug(f"Analyzer: Raw Gemini response text: {response.text}")
        
        # Parse the JSON response
        extracted_data = json.loads(response.text)
        
        # Basic validation - check for required fields
        if not isinstance(extracted_data, dict):
            raise ValueError("Response is not a valid JSON object")
            
        if "call_type" not in extracted_data:
            raise ValueError("Response missing required 'call_type' field")
            
        if extracted_data["call_type"] not in call_types:
            logger.warning(f"Invalid call type '{extracted_data['call_type']}'. Using 'Others' instead.")
            extracted_data["call_type"] = "Others"
        
        logger.info(f"Successfully analyzed transcript for tenant '{tenant}'.")
        return extracted_data

    except json.JSONDecodeError as e:
        logger.error(f"Analyzer: Failed to decode JSON from Gemini response. Error: {e}. Response text: {response.text if 'response' in locals() else 'No response'}")
        return {"call_type": "Others", "summary": "Failed to analyze call due to JSON decoding error", "key_details": {}}
        
    except Exception as e:
        logger.error(f"Analyzer: An unexpected error occurred during transcript analysis: {e}")
        return {"call_type": "Others", "summary": "Failed to analyze call due to an unexpected error", "key_details": {}}
