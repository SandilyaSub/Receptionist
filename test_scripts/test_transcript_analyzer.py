#!/usr/bin/env python3
"""
Test script for the new transcript analyzer implementation.
This script tests the transcript analyzer with a sample transcript.
"""

import os
import sys
import json
import asyncio
import logging
from dotenv import load_dotenv

# Add the parent directory to the path so we can import the transcript_analyzer module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcript_analyzer import analyze_transcript

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sample transcript for testing
SAMPLE_TRANSCRIPT = """
AI: Hello! Thank you for calling Lovely Bakery. This is your virtual assistant. How can I help you today?

Customer: Hi, I'd like to order a birthday cake for my daughter's party this weekend.

AI: That's wonderful! I'd be happy to help you order a birthday cake. Could you please tell me what day you need the cake for?

Customer: We need it for Saturday afternoon. The party starts at 3 PM.

AI: Great! Saturday afternoon it is. What kind of cake would you like? We have chocolate, vanilla, red velvet, and our special rainbow cake that's very popular for children's birthdays.

Customer: I think she'd love the rainbow cake. She's turning 8 and loves colorful things.

AI: The rainbow cake is an excellent choice for an 8-year-old's birthday! Would you like any specific message written on the cake?

Customer: Yes, please write "Happy 8th Birthday, Emma!"

AI: Perfect! I've noted that you'd like a rainbow cake with "Happy 8th Birthday, Emma!" written on it for this Saturday afternoon. What size cake would you prefer? We have small (serves 8-10), medium (serves 15-20), or large (serves 25-30).

Customer: I think medium would be good. We're expecting about 15 kids plus some parents.

AI: A medium rainbow cake is a great choice for your group size. Would you like to add any special decorations? We offer fondant flowers, chocolate figurines, or fresh fruit toppings at an additional cost.

Customer: Could you add some fondant flowers in pink and purple? Those are her favorite colors.

AI: Absolutely! I'll add pink and purple fondant flowers to your order. Is there anything else you'd like to add to your order?

Customer: No, that's all for now.

AI: Great! Let me summarize your order: A medium rainbow cake with "Happy 8th Birthday, Emma!" written on it, decorated with pink and purple fondant flowers, to be picked up this Saturday afternoon for a 3 PM party. Is that correct?

Customer: Yes, that's perfect.

AI: Wonderful! Could I please have your name and a contact number for this order?

Customer: My name is Sarah Johnson and my number is 555-123-4567.

AI: Thank you, Sarah. I've created your order for the medium rainbow birthday cake. The total comes to $45.99. You can pay when you pick up the cake on Saturday. We recommend coming about 30 minutes before your event, so around 2:30 PM would be ideal. Is there anything else you'd like to know?

Customer: No, that's all. Thank you for your help!

AI: You're very welcome! Thank you for choosing Lovely Bakery for Emma's special day. We look forward to seeing you on Saturday. Have a wonderful day!

Customer: You too, goodbye!

AI: Goodbye!
"""

async def test_transcript_analyzer():
    """Test the transcript analyzer with a sample transcript."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get the API key from environment variables
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables.")
        return
    
    # Test with bakery tenant
    tenant = "bakery"
    
    logger.info(f"Testing transcript analyzer with tenant: {tenant}")
    logger.info("Sample transcript length: %d characters", len(SAMPLE_TRANSCRIPT))
    
    # Call the analyzer
    result = await analyze_transcript(SAMPLE_TRANSCRIPT, tenant, api_key)
    
    if result:
        # Pretty print the result
        logger.info("Analysis result:")
        print(json.dumps(result, indent=2))
        
        # Validate the result structure
        if "call_type" in result:
            logger.info(f"Call type: {result['call_type']}")
        else:
            logger.error("Missing call_type in result")
            
        if "summary" in result:
            logger.info(f"Summary: {result['summary']}")
        else:
            logger.error("Missing summary in result")
            
        if "key_details" in result:
            logger.info(f"Key details count: {len(result['key_details'])}")
        else:
            logger.error("Missing key_details in result")
    else:
        logger.error("Transcript analysis failed.")

if __name__ == "__main__":
    asyncio.run(test_transcript_analyzer())
