"""
Main Prompt Generator Interface

Orchestrates the complete prompt generation pipeline:
Template Generation → LLM Refinement → Quality Validation
"""

import os
import json
import argparse
import sys
from typing import Optional, Dict, Any
from datetime import datetime

import dotenv

dotenv.load_dotenv()

from business_schema import BusinessData, GeneratedPrompt, EXAMPLE_BUSINESS_DATA
from template_generator import PromptTemplateGenerator
from llm_refiner import ClaudePromptRefiner

class PromptGenerator:
    """Main interface for automated prompt generation."""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize the prompt generation pipeline."""
        self.template_generator = PromptTemplateGenerator()
        
        # Initialize Claude refiner if API key is available
        self.claude_refiner = None
        try:
            self.claude_refiner = ClaudePromptRefiner(os.getenv("ANTHROPIC_API_KEY"))
        except ValueError as e:
            print(f"Warning: Claude refiner not available - {e}")
            print("Will use template-only generation")
    
    def generate_agent_prompt(self, business_data: BusinessData, business_input_text: str = None, use_llm_refinement: bool = True) -> GeneratedPrompt:
        """
        Generate a complete AI agent prompt for the given business using data-first approach.
        
        Args:
            business_data: Business information from onboarding
            business_input_text: Raw business input text from file
            use_llm_refinement: Whether to use Claude for generation (default: True)
            
        Returns:
            GeneratedPrompt object with the final prompt and metadata
        """
        
        # Use data-first approach if LLM is available and requested
        if use_llm_refinement and self.claude_refiner and business_input_text:
            print("Generating prompt with Claude 4 Sonnet (data-first approach)...")
            try:
                generated_prompt = self.claude_refiner.generate_prompt_data_first(business_input_text, business_data)
                print("✅ Data-first prompt generation completed successfully")
                return generated_prompt
            except Exception as e:
                print(f"⚠️ LLM generation failed: {e}")
                print("Falling back to template generation")
        
        # Fallback: Generate base template (legacy approach)
        print(f"Generating base template for {business_data.business_name}...")
        base_template = self.template_generator.generate_base_template(business_data)
        
        fallback_prompt = GeneratedPrompt(
            prompt_text=base_template,
            business_data=business_data,
            generation_timestamp=datetime.now().isoformat(),
            quality_score=0.6,  # Lower score for template fallback
            validation_notes=["Generated from template (fallback - LLM not available or failed)"]
        )
        
        return fallback_prompt
    
    def generate_from_onboarding_data(self, onboarding_json: Dict[str, Any]) -> GeneratedPrompt:
        """
        Generate prompt from raw onboarding form data.
        
        Args:
            onboarding_json: Raw data from the onboarding form
            
        Returns:
            GeneratedPrompt object
        """
        
        # Convert onboarding data to BusinessData structure
        business_data = self._parse_onboarding_data(onboarding_json)
        
        # Generate the prompt
        return self.generate_agent_prompt(business_data)
    
    def _parse_onboarding_data(self, onboarding_json: Dict[str, Any]) -> BusinessData:
        """Parse raw onboarding form data into BusinessData structure."""
        
        # This would map the actual onboarding form fields to BusinessData
        # For now, using example mapping - adjust based on actual form structure
        
        from business_schema import BusinessType, LanguageCode
        
        # Map business type
        business_type_mapping = {
            "healthcare": BusinessType.HEALTHCARE,
            "dental": BusinessType.HEALTHCARE,
            "medical": BusinessType.HEALTHCARE,
            "food": BusinessType.FOOD_BEVERAGE,
            "restaurant": BusinessType.FOOD_BEVERAGE,
            "bakery": BusinessType.FOOD_BEVERAGE,
            "education": BusinessType.EDUCATION,
            "college": BusinessType.EDUCATION,
            "school": BusinessType.EDUCATION,
            "beauty": BusinessType.BEAUTY_WELLNESS,
            "salon": BusinessType.BEAUTY_WELLNESS,
            "spa": BusinessType.BEAUTY_WELLNESS
        }
        
        # Map languages
        language_mapping = {
            "english": LanguageCode.ENGLISH,
            "hindi": LanguageCode.HINDI,
            "telugu": LanguageCode.TELUGU,
            "tamil": LanguageCode.TAMIL,
            "kannada": LanguageCode.KANNADA,
            "malayalam": LanguageCode.MALAYALAM,
            "marathi": LanguageCode.MARATHI,
            "gujarati": LanguageCode.GUJARATI,
            "bengali": LanguageCode.BENGALI,
            "punjabi": LanguageCode.PUNJABI
        }
        
        # Extract and map data
        business_name = onboarding_json.get("business_name", "")
        business_type_str = onboarding_json.get("business_type", "").lower()
        business_type = business_type_mapping.get(business_type_str, BusinessType.OTHER)
        
        # Parse languages
        supported_languages = []
        language_list = onboarding_json.get("languages", [])
        if isinstance(language_list, str):
            language_list = [language_list]
        
        for lang in language_list:
            mapped_lang = language_mapping.get(lang.lower())
            if mapped_lang:
                supported_languages.append(mapped_lang)
        
        if not supported_languages:
            supported_languages = [LanguageCode.ENGLISH]  # Default
        
        # Parse services
        services = onboarding_json.get("services", [])
        if isinstance(services, str):
            services = [services]
        
        # Create BusinessData object
        business_data = BusinessData(
            business_name=business_name,
            business_type=business_type,
            location=onboarding_json.get("location", ""),
            phone_number=onboarding_json.get("phone_number", ""),
            working_hours=onboarding_json.get("working_hours", "9 AM - 6 PM"),
            website=onboarding_json.get("website"),
            services=services,
            products=onboarding_json.get("products"),
            pricing_info=onboarding_json.get("pricing_info"),
            primary_language=supported_languages[0],
            supported_languages=supported_languages,
            welcome_message=onboarding_json.get("welcome_message"),
            business_description=onboarding_json.get("business_description", ""),
            special_instructions=onboarding_json.get("special_instructions"),
            appointment_required=onboarding_json.get("appointment_required", False),
            online_booking_available=onboarding_json.get("online_booking_available", False),
            payment_methods=onboarding_json.get("payment_methods"),
            delivery_available=onboarding_json.get("delivery_available", False),
            custom_fields=onboarding_json.get("custom_fields")
        )
        
        return business_data
    
    def save_prompt_to_output_directory(self, generated_prompt: GeneratedPrompt, tenant_id: str) -> str:
        """
        Save the generated prompt to the output directory (not production).
        
        Args:
            generated_prompt: The generated prompt object
            tenant_id: Unique identifier for the tenant
            
        Returns:
            Path where the prompt was saved
        """
        
        # Create output directory structure
        base_dir = "/Users/sandilya/CascadeProjects/receptionist_lovable/prompt_generation"
        output_dir = f"{base_dir}/output_prompts/{tenant_id}"
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the prompt
        prompt_path = f"{output_dir}/assistant.txt"
        generated_prompt.save_to_file(prompt_path)
        
        # Save metadata
        metadata = {
            "tenant_id": tenant_id,
            "business_name": generated_prompt.business_data.business_name,
            "generation_timestamp": generated_prompt.generation_timestamp,
            "quality_score": generated_prompt.quality_score,
            "validation_notes": generated_prompt.validation_notes,
            "business_type": generated_prompt.business_data.business_type.value,
            "location": generated_prompt.business_data.location
        }
        
        metadata_path = f"{output_dir}/metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Generated prompt saved to: {prompt_path}")
        print(f"✅ Metadata saved to: {metadata_path}")
        print(f"📋 Review the prompt and manually copy to production when ready")
        
        return prompt_path
    
    def load_business_data_from_file(self, input_file_path: str) -> BusinessData:
        """
        Load business data from a text file containing onboarding information.
        
        Expected format:
        business_name: Sreedevi Dental Clinic
        business_type: healthcare
        location: Rajahmundry
        phone_number: +91-9876543210
        working_hours: 9:00 AM - 6:00 PM, Monday to Saturday
        services: General dental consultation, Teeth cleaning, Root canal treatment
        languages: Telugu, English, Hindi
        business_description: Premier dental care clinic
        special_instructions: Always ask about dental history
        appointment_required: true
        
        Args:
            input_file_path: Path to the input text file
            
        Returns:
            BusinessData object parsed from the file
        """
        
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"Input file not found: {input_file_path}")
        
        # Read and parse the input file
        business_info = {}
        with open(input_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    key, value = line.split(':', 1)
                    business_info[key.strip().lower()] = value.strip()
        
        # Convert to BusinessData using the existing parsing logic
        return self._parse_onboarding_data(business_info)

# Example usage and testing
def test_prompt_generation():
    """Test the complete prompt generation pipeline."""
    
    print("🚀 Testing Automated Prompt Generation Pipeline")
    print("=" * 60)
    
    # Initialize generator
    generator = PromptGenerator()
    
    # Test with sample input file
    sample_input_path = "/Users/sandilya/CascadeProjects/receptionist_lovable/prompt_generation/sample_input.txt"
    
    try:
        # Load business data and raw input text
        business_data = generator.load_business_data_from_file(sample_input_path)
        with open(sample_input_path, 'r', encoding='utf-8') as f:
            business_input_text = f.read()
        
        print(f"Generating prompt for: {business_data.business_name}")
        print(f"Business Type: {business_data.business_type.value}")
        print(f"Location: {business_data.location}")
        print()
        
        # Generate prompt using data-first approach
        generated_prompt = generator.generate_agent_prompt(business_data, business_input_text)
        
    except FileNotFoundError:
        print("Sample input file not found, using example business data...")
        # Fallback to example data
        generated_prompt = generator.generate_agent_prompt(EXAMPLE_BUSINESS_DATA)
    
    # Display results
    print("📋 Generation Results:")
    print(f"Quality Score: {generated_prompt.quality_score}")
    print(f"Generation Time: {generated_prompt.generation_timestamp}")
    print(f"Validation Notes: {generated_prompt.validation_notes}")
    print()
    
    # Show preview of generated prompt
    prompt_preview = generated_prompt.prompt_text[:800] + "..." if len(generated_prompt.prompt_text) > 800 else generated_prompt.prompt_text
    print("📝 Generated Prompt Preview:")
    print("-" * 40)
    print(prompt_preview)
    print()
    
    # Save to tenant repository
    test_tenant_id = "sreedevi_dental_rjy"
    saved_path = generator.save_prompt_to_tenant_repository(generated_prompt, test_tenant_id)
    
    print(f"💾 Prompt saved successfully to tenant repository!")
    print(f"Path: {saved_path}")
    
    return generated_prompt

def main():
    """Main CLI function for prompt generation."""
    parser = argparse.ArgumentParser(
        description='Generate AI agent prompts from business onboarding data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 prompt_generator.py --input business_data.txt --tenant sreedevi_dental_rjy
  python3 prompt_generator.py --test  # Run with example data
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        help='Path to input text file containing business onboarding data'
    )
    
    parser.add_argument(
        '--tenant', '-t',
        type=str,
        help='Tenant ID for the business (used for output directory name)'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run with example data (ignores --input and --tenant)'
    )
    
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Skip LLM refinement, use template only'
    )
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = PromptGenerator()
    
    if args.test:
        # Run test with example data
        print("🧪 Running test with example business data...")
        generated_prompt = test_prompt_generation()
        return
    
    # Validate required arguments
    if not args.input:
        print("❌ Error: --input file is required (or use --test for example)")
        parser.print_help()
        sys.exit(1)
    
    if not args.tenant:
        print("❌ Error: --tenant ID is required (or use --test for example)")
        parser.print_help()
        sys.exit(1)
    
    try:
        # Load business data from input file
        print(f"📖 Loading business data from: {args.input}")
        business_data = generator.load_business_data_from_file(args.input)
        
        # Also read the raw input text for data-first approach
        with open(args.input, 'r', encoding='utf-8') as f:
            business_input_text = f.read()
        
        print(f"✅ Loaded data for: {business_data.business_name}")
        print(f"   Business Type: {business_data.business_type.value}")
        print(f"   Location: {business_data.location}")
        print(f"   Services: {len(business_data.services)} services listed")
        print()
        
        # Generate prompt
        use_llm = not args.no_llm
        print(f"🚀 Generating prompt (LLM approach: {'data-first' if use_llm else 'template-only'})...")
        
        generated_prompt = generator.generate_agent_prompt(business_data, business_input_text, use_llm_refinement=use_llm)
        
        # Save to output directory
        output_path = generator.save_prompt_to_output_directory(generated_prompt, args.tenant)
        
        print()
        print("🎉 Prompt generation completed successfully!")
        print(f"📁 Output saved to: {output_path}")
        print(f"📋 Review the generated prompt and copy to production when ready")
        
    except FileNotFoundError as e:
        print(f"❌ File Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Generation Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
