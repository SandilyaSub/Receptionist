"""
LLM Refiner for AI Agent Prompts

Uses Claude 3.5 Sonnet to refine and enhance base prompt templates
using exemplar prompts as few-shot learning references.
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import local modules
from business_schema import BusinessData, GeneratedPrompt
from character_count_scorer import CharacterCountScorer

class ClaudePromptRefiner:
    """Refines prompt templates using Claude 4 Sonnet."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Claude client."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        
        # Initialize character count scorer
        self.char_scorer = CharacterCountScorer()
        
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
    
    def _load_common_instructions(self, include_calendar: bool = False) -> str:
        """Load common instructions from file with fallback to hardcoded backup."""
        
        # Try to load from common_input.txt file
        try:
            common_input_path = os.path.join(os.path.dirname(__file__), "common_input.txt")
            with open(common_input_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  # Ensure file is not empty
                    print("✅ Loaded common instructions from common_input.txt")
                    # Filter out calendar instructions if not requested
                    if not include_calendar:
                        # Remove calendar-specific sections
                        lines = content.split('\n')
                        filtered_lines = []
                        skip_section = False
                        
                        for line in lines:
                            if 'CALENDAR' in line.upper() or 'APPOINTMENT' in line.upper():
                                skip_section = True
                            elif line.strip() == '' and skip_section:
                                skip_section = False
                            elif not skip_section:
                                filtered_lines.append(line)
                        
                        content = '\n'.join(filtered_lines)
                    
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
    
    def _create_data_first_prompt(self, business_input_text: str, include_calendar: bool = False) -> str:
        """Create the data-first prompt for Claude using raw business input and structured framework."""
        
        # Load common instructions from file or fallback
        common_instructions = self._load_common_instructions(include_calendar)
        
        # Add calendar functions if requested
        calendar_section = ""
        if include_calendar:
            try:
                from calendar_functions_loader import get_generic_calendar_functions_json, get_generic_calendar_instructions
                calendar_functions = get_generic_calendar_functions_json()
                calendar_instructions = get_generic_calendar_instructions()
                calendar_section = f"""

CALENDAR FUNCTIONS AVAILABLE:
{calendar_functions}

{calendar_instructions}"""
            except ImportError:
                print("Warning: Could not load calendar functions")
        
        data_first_prompt = f"""You are a world class system instructions generator building system instructions for the best in class AI voice agent.

This AI agent is built on Gemini's streaming API capabilities for real-time voice interactions.

Below are the business inputs about the business:

{business_input_text}

{common_instructions}{calendar_section}

CRITICAL CSV FORMAT PRESERVATION:
- If the input contains CSV format for doctor/specialist information (Specialization,Name,Email,Working Hours,Days Off), preserve this EXACT format in the system instructions
- If the input contains CSV format for escalation/handover information (Department,PhoneNumber), preserve this EXACT format in the system instructions  
- Do NOT convert CSV data into bullet points or other formats - maintain the original CSV structure
- CSV format provides higher accuracy during actual voice calls and testing

CRITICAL ESCALATION PROTOCOL:
- You MUST use the handover_transfer_call function for ALL escalations and transfers
- Don't wait or ask for additional details. Transfer immediately when escalation is needed
- Never simulate or assume a transfer without calling the handover_transfer_call function
- Use imperative language: "Transferring you now to [Department]" not "Let me transfer you"
- For emergencies: "Transferring immediately to Emergency" 
- If function fails, apologize and advise to call hospital directly
- Emergency transfers take priority over all other operations

CRITICAL REQUIREMENTS FOR STRUCTURED OUTPUT:

1. **Follow the Framework Structure Exactly**: Use the section headers provided in the framework above
2. **Use Bullet Points**: Prefer clear bullet points over paragraphs for better instruction following
3. **Function Call Requirements**: {"If calendar functions are provided, include:" if include_calendar else "For handover and escalation scenarios:"}
   - {"MANDATORY calendar function usage for all appointment operations" if include_calendar else "MANDATORY handover_transfer_call function usage for all escalations"}
   - {"Function call error handling and fallback procedures" if include_calendar else "Immediate transfer protocols without conversational delays"}
   - {"Clear function usage rules with ✅ MUST DO and ❌ NEVER DO indicators" if include_calendar else "Imperative action commands for emergency scenarios"}
4. **Conversation Flow**: Define clear phases with goals and exit criteria
5. **Language Implementation**: Start in FIRST mentioned language, switch when customer switches
6. **Complete Business Data**: Include ALL provided information - services, pricing, provider details, etc.
7. **Cultural Authenticity**: Proper Indian context, honorifics, regional expressions
8. **Variety Rules**: Add instructions to avoid repetitive phrasing
9. **NO INTRODUCTORY GREETING**: Do NOT include opening lines like "Namaste! Thank you for calling..." in the system instructions - these will be handled by the application code
10. **CSV FORMAT PRESERVATION**: If CSV data exists for specialists/doctors or escalation info, preserve the EXACT CSV format - do NOT convert to bullet points

SPECIFIC FORMATTING REQUIREMENTS:
- Use # for main section headers
- Use ## for subsections  
- Use - or • for bullet points
- Use ✅ for DO rules and ❌ for DON'T rules
- Capitalize key terms for emphasis
- Include sample phrases for natural conversation flow

OUTPUT REQUIREMENTS:
- Generate ONLY the system instructions text
- No meta-commentary or explanations
- Ready to deploy for production voice AI
- Follow the structured framework sections
- Include conversation flow phases with clear exit criteria
- {"Add tool call preambles and function usage instructions" if include_calendar else "Focus on customer service excellence"}
- EXCLUDE any introductory greeting text - this is handled separately

Generate the comprehensive structured system instructions now:"""

        return data_first_prompt
    
    def refine_prompt_data_first(self, business_input_text: str, include_calendar: bool = False) -> GeneratedPrompt:
        """Generate prompt using data-first approach - feed all business data directly to Claude."""
        
        try:
            # Create the data-first prompt
            data_first_prompt = self._create_data_first_prompt(business_input_text, include_calendar)
            
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
            
            # Calculate a detailed quality score with breakdown
            quality_analysis = self._calculate_quality_score(generated_prompt_text, business_input_text)
            quality_score = quality_analysis["quality_score"]
            
            # Create GeneratedPrompt object (business_data not available in data-first approach)
            generated_prompt = GeneratedPrompt(
                prompt_text=generated_prompt_text,
                business_data=None,  # Not available in data-first approach
                generation_timestamp=datetime.now().isoformat(),
                quality_score=quality_score,
                validation_notes=["Generated using data-first approach with Claude"],
                metadata={"scoring_breakdown": quality_analysis["breakdown"]}
            )
            
            return generated_prompt
            
        except Exception as e:
            raise Exception(f"Error generating prompt with Claude: {str(e)}")
    
    def _calculate_quality_score(self, generated_prompt: str, business_input: str) -> dict:
        """Calculate quality score based on structured prompt best practices."""
        
        score = 0.0
        max_score = 12.0
        breakdown = {}
        
        # Check for structured sections (OpenAI best practices)
        required_sections = ["# ROLE & OBJECTIVE", "# PERSONALITY & TONE", "# CONTEXT", "# INSTRUCTIONS", "# CONVERSATION FLOW"]
        sections_found = sum(1 for section in required_sections if section in generated_prompt)
        section_score = (sections_found / len(required_sections)) * 3.0
        score += section_score
        breakdown["structured_sections"] = {
            "score": section_score,
            "max_score": 3.0,
            "found_sections": sections_found,
            "total_sections": len(required_sections),
            "details": f"Found {sections_found}/{len(required_sections)} required sections"
        }
        
        # Check for tool call optimization
        tool_score = 0.0
        tool_found = 0
        if "appointment" in business_input.lower():
            tool_indicators = ["✅", "❌", "Let me check", "proactive"]
            tool_found = sum(1 for indicator in tool_indicators if indicator in generated_prompt)
            tool_score = min(tool_found / len(tool_indicators), 1.0) * 2.0
            score += tool_score
        breakdown["tool_optimization"] = {
            "score": tool_score,
            "max_score": 2.0,
            "applicable": "appointment" in business_input.lower(),
            "details": f"Tool indicators found: {tool_found if 'appointment' in business_input.lower() else 'N/A (no appointments)'}"
        }
        
        # Check for conversation flow phases
        flow_indicators = ["Greeting", "Information Gathering", "Action", "Confirmation", "Exit when"]
        flow_found = sum(1 for indicator in flow_indicators if indicator in generated_prompt)
        flow_score = (flow_found / len(flow_indicators)) * 2.0
        score += flow_score
        breakdown["conversation_flow"] = {
            "score": flow_score,
            "max_score": 2.0,
            "found_phases": flow_found,
            "total_phases": len(flow_indicators),
            "details": f"Found {flow_found}/{len(flow_indicators)} conversation phases"
        }
        
        # Check for bullet points vs paragraphs (better instruction following)
        bullet_count = generated_prompt.count("- ") + generated_prompt.count("• ")
        bullet_score = 1.0 if bullet_count > 10 else 0.0
        score += bullet_score
        breakdown["bullet_points"] = {
            "score": bullet_score,
            "max_score": 1.0,
            "bullet_count": bullet_count,
            "details": f"Found {bullet_count} bullet points (good if >10)"
        }
        
        # Check for cultural elements (updated to match Gemini)
        cultural_elements = ["Namaste", "ji", "sir", "madam", "Telugu"]
        cultural_found = sum(1 for element in cultural_elements if element in generated_prompt)
        cultural_score = min(cultural_found / len(cultural_elements), 1.0) * 1.0
        score += cultural_score
        breakdown["cultural_elements"] = {
            "score": cultural_score,
            "max_score": 1.0,
            "found_elements": cultural_found,
            "total_elements": len(cultural_elements),
            "details": f"Found {cultural_found}/{len(cultural_elements)} cultural elements"
        }
        
        # Check for business data inclusion (₹ or Rs.)
        has_pricing_input = ("₹" in business_input or "Rs." in business_input or "rs." in business_input.lower())
        has_pricing_output = ("₹" in generated_prompt or "Rs." in generated_prompt or "rs." in generated_prompt.lower())
        business_score = 1.0 if (has_pricing_input and has_pricing_output) else 0.0
        score += business_score
        breakdown["business_data_inclusion"] = {
            "score": business_score,
            "max_score": 1.0,
            "details": "Pricing symbols (₹/Rs.) preserved from input" if business_score > 0 else "No pricing data or not preserved"
        }
        
        # Check for sample phrases (better UX)
        sample_score = 1.0 if ("sample phrases" in generated_prompt.lower() or "preamble" in generated_prompt.lower()) else 0.0
        score += sample_score
        breakdown["sample_phrases"] = {
            "score": sample_score,
            "max_score": 1.0,
            "details": "Contains sample phrases or preambles" if sample_score > 0 else "Missing sample phrases/preambles"
        }
        
        # Check for variety rules (reduces repetition)
        variety_score = 1.0 if ("variety" in generated_prompt.lower() or "avoid repetit" in generated_prompt.lower()) else 0.0
        score += variety_score
        breakdown["variety_rules"] = {
            "score": variety_score,
            "max_score": 1.0,
            "details": "Contains variety/anti-repetition rules" if variety_score > 0 else "Missing variety rules"
        }
        
        char_score_result = self.char_scorer.calculate_character_score(generated_prompt)
        char_score = char_score_result["score"]
        char_max_score = char_score_result["max_score"]
        score += char_score
        breakdown["character_score"] = {
            "score": char_score,
            "max_score": char_max_score,
            "total_score": (section_score + tool_score + flow_score + bullet_score + 
                      cultural_score + business_score + sample_score + variety_score + char_score)
        }
        max_total_score = 15.0  # Updated from 13.0 to 15.0 (character scoring now 3 points))  # Normalize to 0-1 range
        
        # Calculate final quality score with updated 15-point maximum
        total_score = (section_score + tool_score + flow_score + bullet_score + 
                      cultural_score + business_score + sample_score + variety_score + char_score)
        max_total_score = 15.0  # Updated from 13.0 to 15.0 (character scoring now 3 points)
        quality_score = total_score / max_total_score
        
        return {
            "quality_score": quality_score,
            "total_score": total_score,
            "max_possible_score": max_total_score,
            "breakdown": breakdown
        }
    
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
