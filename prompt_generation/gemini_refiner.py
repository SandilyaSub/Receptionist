"""
Gemini Prompt Refiner

Uses Google's Gemini 2.5 Pro with thinking enabled to refine and generate
high-quality AI agent prompts from business data.
"""

import os
import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Import local modules
from business_schema import BusinessData, GeneratedPrompt
from telugu_script_filter import clean_telugu_script_from_prompt, validate_no_telugu_script
from character_count_scorer import CharacterCountScorer
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold


class GeminiPromptRefiner:
    """Refines prompts using Google's Gemini 2.5 Flash model."""
    
    def __init__(self):
        """Initialize the Gemini client."""
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        genai.configure(api_key=api_key)
        
        # Initialize character count scorer
        self.char_scorer = CharacterCountScorer()
        
        # Configure the model
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 8192,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
    
    def refine_prompt(self, business_input_text: str, include_calendar: bool = False) -> GeneratedPrompt:
        """
        Generate a refined prompt using Gemini 2.5 Flash.
        
        Args:
            business_input_text: Raw business data text
            include_calendar: Whether to include calendar functionality
            
        Returns:
            GeneratedPrompt object with refined content and metadata
        """
        print("Generating prompt with Gemini 2.5 Flash (data-first approach)...")
        
        try:
            # Load common instructions
            common_instructions = self._load_common_instructions()
            
            # Create the data-first prompt
            prompt_text = self._create_data_first_prompt(business_input_text, include_calendar)
            
            # Generate content with Gemini
            start_time = time.time()
            response = self.model.generate_content(prompt_text)
            generation_time = time.time() - start_time
            
            # Extract the generated content
            if not response.text:
                raise Exception("Gemini returned empty response")
            
            refined_content = response.text.strip()
            
            # Calculate token usage (approximate for Gemini)
            input_tokens = len(prompt_text.split()) * 1.3  # Rough approximation
            output_tokens = len(refined_content.split()) * 1.3
            
            # Create metadata
            metadata = {
                "model": "gemini-2.5-flash",
                "approach": "data-first",
                "generation_time_seconds": round(generation_time, 2),
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "total_tokens": int(input_tokens + output_tokens),
                "include_calendar": include_calendar,
                "timestamp": datetime.now().isoformat(),
                "quality_score": self._calculate_quality_score(refined_content, business_input_text)["quality_score"],
                "scoring_breakdown": self._calculate_quality_score(refined_content, business_input_text)["breakdown"]
            }
            
            scoring_result = self._calculate_quality_score(refined_content, business_input_text)
            
            # Clean Telugu script from the generated prompt
            cleaned_content = clean_telugu_script_from_prompt(refined_content)
            
            # Validate no Telugu script remains
            is_valid, telugu_lines = validate_no_telugu_script(cleaned_content)
            validation_notes = ["Generated using data-first approach with Gemini 2.5 Flash"]
            
            if not is_valid:
                print(f"⚠️ Warning: Telugu script detected and cleaned from {len(telugu_lines)} lines")
                validation_notes.append(f"Telugu script cleaned from {len(telugu_lines)} lines")
            
            # Recalculate quality score with cleaned content
            final_scoring_result = self._calculate_quality_score(cleaned_content, business_input_text)
            
            return GeneratedPrompt(
                prompt_text=cleaned_content,
                business_data=None,
                generation_timestamp=datetime.now().isoformat(),
                quality_score=final_scoring_result["quality_score"],
                validation_notes=validation_notes,
                metadata={"scoring_breakdown": final_scoring_result["breakdown"]}
            )
            
        except Exception as e:
            print(f"❌ Gemini generation failed: {e}")
            raise
    
    def _load_common_instructions(self) -> str:
        """Load common instructions from file."""
        try:
            common_file_path = os.path.join(os.path.dirname(__file__), 'common_input.txt')
            with open(common_file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print("⚠️ Warning: common_input.txt not found, using default instructions")
            return "Follow OpenAI Realtime API best practices for system instructions."
    
    def _create_data_first_prompt(self, business_input_text: str, include_calendar: bool = False) -> str:
        """Create the data-first prompt for Gemini."""
        common_instructions = self._load_common_instructions()
        
        # Load calendar functions if requested
        calendar_section = ""
        if include_calendar:
            try:
                from calendar_functions_loader import get_generic_calendar_instructions
                calendar_instructions = get_generic_calendar_instructions()
                calendar_section = f"\n\n{calendar_instructions}"
            except ImportError:
                print("⚠️ Warning: Calendar functions not available")
        
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
3. **NO JSON FORMAT**: Do not include any JSON function definitions in the system instructions. Function calling definitions are provided separately at model initialization.
4. **English Only with Transliterated Telugu**: Write all system instructions in English only. Do NOT include any Telugu Devanagari script text. Only use transliterated Telugu (Roman script) in examples and sample phrases.
5. **Function Call Requirements**: {"If calendar functions are provided, include:" if include_calendar else "For handover and escalation scenarios:"}
   - {"MANDATORY calendar function usage for all appointment operations" if include_calendar else "MANDATORY handover_transfer_call function usage for all escalations"}
   - {"Function call error handling and fallback procedures" if include_calendar else "Immediate transfer protocols without conversational delays"}
   - {"Clear function usage rules with DO and DON'T indicators" if include_calendar else "Imperative action commands for emergency scenarios"}
6. **Conversation Flow**: Define clear phases with goals and exit criteria
7. **Language Implementation**: Start in FIRST mentioned language, switch when customer switches
8. **Sample Phrases**: Use transliterated Telugu in examples only, not in instructions

Generate comprehensive system instructions that will create an exceptional AI voice agent for this business. Focus on practical, actionable instructions that will result in smooth, natural conversations and successful customer interactions.

The output should be ready-to-use system instructions that can be directly implemented in a production voice AI system."""

        return data_first_prompt
    
    def _calculate_quality_score(self, generated_prompt: str, business_input: str = "") -> dict:
        """Calculate quality score based on structured prompt best practices (same as Claude methodology)."""
        
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
        
        # Check for cultural elements
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
        
        # Calculate overall score (out of 13 points total now)
        total_score = (
            section_score + tool_score + flow_score + 
            bullet_score + cultural_score + business_score + 
            sample_score + variety_score + char_score
        )
        max_total_score = 15.0  # Updated from 13.0 to 15.0 (character scoring now 3 points)
        quality_score = total_score / max_total_score
        
        return {
            "quality_score": quality_score,
            "total_score": total_score,
            "max_possible_score": max_total_score,
            "breakdown": breakdown
        }
