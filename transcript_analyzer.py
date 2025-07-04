import os
import asyncio
import logging
import json
from typing import Optional, Dict, Any

from google import genai
from google.genai import types
from jsonschema import validate, ValidationError
from supabase import create_client, Client

# Get a logger instance
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

async def fetch_analyzer_schema(tenant_id: str, supabase: Client) -> Optional[Dict[str, Any]]:
    """Fetches the analyzer JSON schema for a given tenant from Supabase."""
    try:
        # Run the synchronous Supabase call in a separate thread
        response = await asyncio.to_thread(
            supabase.table("tenant_configs")
            .select("analyzer_schema")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .single()
            .execute
        )
        if response.data and "analyzer_schema" in response.data:
            logger.info(f"Successfully fetched analyzer schema for tenant '{tenant_id}'.")
            return response.data["analyzer_schema"]
        else:
            logger.error(f"No active analyzer schema found for tenant '{tenant_id}'.")
            return None
    except Exception as e:
        logger.error(f"Error fetching schema for tenant '{tenant_id}' from Supabase: {e}")
        return None

# --- Prompt Loader ---
def load_analyzer_prompt(tenant: str, transcript: str, schema: Dict[str, Any]) -> str:
    """Loads the analyzer prompt and injects the transcript and schema."""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), 'tenant_repository', tenant, 'prompts', 'analyzer.txt')
        with open(prompt_path, 'r') as f:
            prompt_template = f.read()
        
        schema_as_string = json.dumps(schema, indent=2)
        return prompt_template.format(transcript=transcript, schema=schema_as_string)
    except FileNotFoundError:
        logger.error(f"Analyzer prompt file not found for tenant '{tenant}'.")
        # Generic fallback if the file is missing
        schema_as_string = json.dumps(schema, indent=2)
        return f"""Analyze the following transcript and extract key details as a JSON object.

Schema:
---
{schema_as_string}
---

Transcript:
---
{transcript}
---
"""

# --- Main Analyzer Function ---
async def analyze_transcript(transcript: str, tenant: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Analyzes a transcript to extract structured data using a dynamically fetched schema."""
    if not transcript:
        logger.warning("Analyzer: Transcript is empty, skipping analysis.")
        return None

    supabase = get_supabase_client()
    if not supabase:
        return None

    schema = await fetch_analyzer_schema(tenant, supabase)
    if not schema:
        # Error is logged in the fetch function
        return None

    prompt = load_analyzer_prompt(tenant, transcript, schema)
    
    logger.info(f"Analyzer: Analyzing transcript for tenant '{tenant}'.")
    logger.debug(f"Analyzer: Prompt sent to Gemini: {prompt[:500]}...")

    try:
        client = genai.Client(api_key=api_key)
        # The `generate_content` method is synchronous. To call it from our async
        # function without blocking the event loop, we use `asyncio.to_thread`.
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        logger.debug(f"Analyzer: Raw Gemini response text: {response.text}")
        
        # The response text is a JSON string, so we need to parse it.
        extracted_data = json.loads(response.text)
        
        # Validate the extracted data against the schema
        validate(instance=extracted_data, schema=schema)
        
        logger.info(f"Successfully analyzed and validated transcript for tenant '{tenant}'.")
        return extracted_data

    except json.JSONDecodeError as e:
        logger.error(f"Analyzer: Failed to decode JSON from Gemini response. Error: {e}. Response text: {response.text}")
        return None
    except ValidationError as e:
        logger.error(f"Analyzer: Gemini response failed schema validation for tenant '{tenant}'. Error: {e}")
        return None
    except Exception as e:
        logger.error(f"Analyzer: An unexpected error occurred during transcript analysis: {e}")
        return None
        return None
