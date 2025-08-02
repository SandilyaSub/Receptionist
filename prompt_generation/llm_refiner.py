"""
LLM Refiner for AI Agent Prompts

Uses Claude 3.5 Sonnet to refine and enhance base prompt templates
using exemplar prompts as few-shot learning references.
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime
import anthropic
from dotenv import load_dotenv

# Load environment variables from root .env file
load_dotenv(dotenv_path="/Users/sandilya/CascadeProjects/receptionist_lovable/.env")

# Import local modules
from business_schema import BusinessData, GeneratedPrompt

class ClaudePromptRefiner:
    """Refines prompt templates using Claude 4 Sonnet."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Claude client."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        
        # Load exemplar prompts for few-shot learning
        self.exemplars = self._load_exemplar_prompts()
    
    def _load_exemplar_prompts(self) -> Dict[str, str]:
        """Load exemplar prompts from the tenant repository."""
        exemplars = {}
        base_path = "/Users/sandilya/CascadeProjects/receptionist_lovable/tenant_repository"
        
        exemplar_tenants = [
            "happy_endings_bellandur",
            "joy_invite", 
            "gsl_college"
        ]
        
        for tenant in exemplar_tenants:
            try:
                prompt_path = f"{base_path}/{tenant}/prompts/assistant.txt"
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    exemplars[tenant] = f.read()
            except FileNotFoundError:
                print(f"Warning: Could not load exemplar prompt for {tenant}")
        
        return exemplars
    
    def _load_common_instructions(self) -> str:
        """Load common instructions from file with fallback to hardcoded backup."""
        
        # Try to load from common_input.txt file
        try:
            common_input_path = os.path.join(os.path.dirname(__file__), "common_input.txt")
            with open(common_input_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  # Ensure file is not empty
                    print("✅ Loaded common instructions from common_input.txt")
                    return content
                else:
                    print("⚠️ common_input.txt is empty, using hardcoded fallback")
                    return self._get_hardcoded_common_instructions()
        except FileNotFoundError:
            print("⚠️ common_input.txt not found, using hardcoded fallback")
            return self._get_hardcoded_common_instructions()
        except Exception as e:
            print(f"⚠️ Error reading common_input.txt: {e}, using hardcoded fallback")
            return self._get_hardcoded_common_instructions()
    
    def _get_hardcoded_common_instructions(self) -> str:
        """Hardcoded fallback common instructions (union of code + file content)."""
        return """
Core Identity & Voice
* Consistent Persona: "You are Aarohi, a warm and professional/enthusiastic receptionist for [Business Name]"
* Indian Cultural Context: Natural Indian English accent, use of "Namaste", cultural sensitivity
* Tone Baseline: Courteous, friendly, patient, solution-oriented
* IST Timezone: All operations and time references in Indian Standard Time

Communication Standards
* Language Matching: Start speaking in the first language mentioned in languages. However if a user switches to a different language , switch to the other language. 
* Clarity Requirements: Speak clearly, moderate pace, natural conversation flow
* Professional Boundaries: Stay within scope of whatever is provided in the attachment. Politely state that you can't answer the out-of-scope queries

Operational Framework
* Scope Limitation: Only speak about information provided in the attachment.
* Information Gathering: Systematic collection of customer details (name, phone, requirements)

Cultural & Regional Adaptations
* Honorifics: Appropriate use of "ji", "sir", "madam" based on context
* Regional Expressions: Adapt to local cultural expressions and formality levels
* Business-Specific Greetings: Start of with the opening sentence provided in the attachment. If one is not provided , then state the opening line - " Namaste ! Thank you for calling [Business_Name] . My name is Aarohi. How can I help you today ? ". Remember that the opening line should be in the first language mentioned in [languages]

PHONE NUMBER HANDLING:
* Do NOT explicitly ask customers for their phone number during the conversation
* If a customer voluntarily shares their phone number, simply acknowledge with: "Thank you, I have noted your number" - do not repeat the number back to them
* If customers ask how they will receive messages/payment links without sharing their number, respond: "Our system has caller ID enabled so we can pick this up from there"
* If they continue asking what their number is, respond: "I cannot share it here for privacy reasons, but don't worry, we have it figured out"
"""
    
    def _create_data_first_prompt(self, business_input_text: str) -> str:
        """Create the data-first prompt for Claude using raw business input and common instructions."""
        
        # Load common instructions from file or fallback
        common_instructions = self._load_common_instructions()
        
        data_first_prompt = f"""You are a world class system instructions generator and you are building system instructions for the best in class AI voice agent.

This AI agent is built on Gemini's streaming API capabilities, so the system instructions are for that.

Below are the business inputs about the business:

{business_input_text}

Please use the following framework to create comprehensive system instructions:

{common_instructions}

IMPORTANT REQUIREMENTS:

1. **Language Implementation**: Start conversations in the FIRST language mentioned in the languages field. If Telugu is first, begin in Telugu.

2. **Complete Business Data**: Include ALL information provided in the business input - pricing details, processes, doctor information, insurance policies, etc. Do not omit any details.

3. **Structured Output**: Create well-organized sections covering:
   - Core Identity & Persona
   - Opening Protocol (in correct language)
   - Business Information (complete details)
   - Services & Pricing (comprehensive)
   - Appointment System & Processes
   - Language Adaptation Guidelines
   - Conversation Management
   - Professional Boundaries

4. **Cultural Authenticity**: Ensure proper Indian context, honorifics, and regional expressions.

5. **Practical Usability**: The output should be immediately deployable for production voice AI interactions.

OUTPUT REQUIREMENTS:
- Provide ONLY the system instructions text
- Do not include explanations, meta-commentary, or markdown formatting
- The output should be ready to save directly as an assistant.txt file
- Include all business details provided in the input
- Ensure the greeting starts in the correct language

Generate the comprehensive system instructions now:"""

        return data_first_prompt
    
    def generate_prompt_data_first(self, business_input_text: str, business_data: BusinessData) -> GeneratedPrompt:
        """Generate prompt using data-first approach - feed all business data directly to Claude."""
        
        try:
            # Create the data-first prompt
            data_first_prompt = self._create_data_first_prompt(business_input_text)
            
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,  # Lower temperature for more consistent output
                messages=[
                    {
                        "role": "user",
                        "content": data_first_prompt
                    }
                ]
            )
            
            # Extract the generated prompt
            generated_prompt_text = response.content[0].text.strip()
            
            # Calculate a basic quality score based on content completeness
            quality_score = self._calculate_quality_score(generated_prompt_text, business_input_text)
            
            # Create GeneratedPrompt object
            generated_prompt = GeneratedPrompt(
                prompt_text=generated_prompt_text,
                business_data=business_data,
                generation_timestamp=datetime.now().isoformat(),
                quality_score=quality_score,
                validation_notes=["Generated using data-first approach with Claude"]
            )
            
            return generated_prompt
            
        except Exception as e:
            raise Exception(f"Error generating prompt with Claude: {str(e)}")
    
    def _calculate_quality_score(self, generated_prompt: str, business_input: str) -> float:
        """Calculate a basic quality score based on content completeness."""
        
        # Basic scoring criteria
        score = 0.0
        max_score = 10.0
        
        # Check for key elements
        if "Aarohi" in generated_prompt:
            score += 1.0
        
        if "Namaste" in generated_prompt or "నమస్కారం" in generated_prompt:
            score += 1.0
        
        if "IST" in generated_prompt or "Indian Standard Time" in generated_prompt:
            score += 1.0
        
        # Check if pricing information is included (if present in input)
        if "₹" in business_input and "₹" in generated_prompt:
            score += 2.0
        
        # Check if language adaptation is mentioned
        if "language" in generated_prompt.lower() and ("Telugu" in generated_prompt or "Hindi" in generated_prompt):
            score += 2.0
        
        # Check if appointment/booking process is mentioned
        if "appointment" in generated_prompt.lower():
            score += 1.0
        
        # Check if business-specific details are included
        if len(generated_prompt) > 2000:  # Comprehensive prompt
            score += 1.0
        
        # Check if proper sections are structured
        section_indicators = ["Core Identity", "Services", "Pricing", "Appointment", "Language"]
        sections_found = sum(1 for indicator in section_indicators if indicator in generated_prompt)
        score += (sections_found / len(section_indicators)) * 1.0
        
        return min(score / max_score, 1.0)  # Normalize to 0-1 range
    
    def batch_refine_prompts(self, templates_and_data: List[tuple]) -> List[GeneratedPrompt]:
        """Refine multiple prompts in batch."""
        results = []
        
        for base_template, business_data in templates_and_data:
            try:
                refined_prompt = self.refine_prompt(base_template, business_data)
                results.append(refined_prompt)
            except Exception as e:
                print(f"Error refining prompt for {business_data.business_name}: {e}")
                # Create a fallback with the base template
                fallback_prompt = GeneratedPrompt(
                    prompt_text=base_template,
                    business_data=business_data,
                    generation_timestamp=datetime.now().isoformat(),
                    quality_score=0.5,  # Lower score for fallback
                    validation_notes=["Used base template due to refinement error"]
                )
                results.append(fallback_prompt)
        
        return results

# Example usage and testing
if __name__ == "__main__":
    from template_generator import PromptTemplateGenerator
    from business_schema import EXAMPLE_BUSINESS_DATA
    
    # Test the complete pipeline
    print("Testing Prompt Generation Pipeline...")
    print("=" * 50)
    
    # Step 1: Generate base template
    generator = PromptTemplateGenerator()
    base_template = generator.generate_base_template(EXAMPLE_BUSINESS_DATA)
    
    print("Base Template Generated:")
    print("-" * 30)
    print(base_template[:500] + "..." if len(base_template) > 500 else base_template)
    print()
    
    # Step 2: Refine with Claude (if API key available)
    try:
        refiner = ClaudePromptRefiner()
        refined_prompt = refiner.refine_prompt(base_template, EXAMPLE_BUSINESS_DATA)
        
        print("Refined Prompt Generated:")
        print("-" * 30)
        print(refined_prompt.prompt_text[:500] + "..." if len(refined_prompt.prompt_text) > 500 else refined_prompt.prompt_text)
        
        # Save to file for inspection
        output_path = "/Users/sandilya/CascadeProjects/receptionist_lovable/prompt_generation/test_output.txt"
        refined_prompt.save_to_file(output_path)
        print(f"\nFull refined prompt saved to: {output_path}")
        
    except Exception as e:
        print(f"Could not test Claude refinement: {e}")
        print("Make sure ANTHROPIC_API_KEY is set in your environment")
