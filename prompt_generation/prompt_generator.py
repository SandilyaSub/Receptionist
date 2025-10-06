"""
Main Prompt Generator Interface

Orchestrates the complete prompt generation pipeline:
Template Generation → LLM Refinement → Quality Validation
"""

import os
import json
import argparse
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime

import dotenv

dotenv.load_dotenv()

from business_schema import BusinessData, GeneratedPrompt, ServiceProviderInfo, EXAMPLE_BUSINESS_DATA
from template_generator import PromptTemplateGenerator
from llm_refiner import ClaudePromptRefiner
from gemini_refiner import GeminiPromptRefiner

class PromptGenerator:
    """Main interface for automated prompt generation."""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize the prompt generation pipeline."""
        self.template_generator = PromptTemplateGenerator()
        
        # Initialize Claude refiner if API key is available
        self.claude_refiner = None
        
        # Initialize Gemini refiner if API key is available
        self.gemini_refiner = None
        try:
            self.claude_refiner = ClaudePromptRefiner(os.getenv("ANTHROPIC_API_KEY"))
        except ValueError as e:
            print(f"Warning: Claude refiner not available - {e}")
            print("Will use template-only generation")
        
        try:
            self.gemini_refiner = GeminiPromptRefiner()
        except ValueError as e:
            print(f"Warning: Gemini refiner not available - {e}")
            print("Will use Claude-only generation")
    
    def generate_agent_prompt(self, business_data: BusinessData, business_input_text: str, use_llm_refinement: bool = True, include_calendar: bool = False, model: str = None) -> Dict[str, GeneratedPrompt]:
        """
        Generate an AI agent prompt using agentic approach with multiple LLMs.
        
        Args:
            business_data: Structured business information
            business_input_text: Raw input text for data-first approach
            use_llm_refinement: Whether to use LLM refinement (default: True)
            include_calendar: Whether to include calendar functionality (default: False)
            model: Specific model to use ('claude' or 'gemini'). If None, uses both models.
            
        Returns:
            Dict[str, GeneratedPrompt]: Dictionary with model names as keys and GeneratedPrompt objects as values
        """
        results = {}
        
        if use_llm_refinement:
            # Generate prompts from specified model(s)
            # Generate with Claude (if requested or no specific model)
            if (model is None or model == 'claude') and self.claude_refiner:
                try:
                    print("🤖 Generating with Claude...")
                    claude_prompt = self.claude_refiner.refine_prompt_data_first(business_input_text, include_calendar)
                    results['claude'] = claude_prompt
                except Exception as e:
                    print(f"❌ Claude generation failed: {e}")
            
            # Generate with Gemini (if requested or no specific model)
            if (model is None or model == 'gemini') and self.gemini_refiner:
                try:
                    print("🧠 Generating with Gemini...")
                    gemini_prompt = self.gemini_refiner.refine_prompt(business_input_text, include_calendar)
                    results['gemini'] = gemini_prompt
                except Exception as e:
                    print(f"❌ Gemini generation failed: {e}")
                    results['gemini'] = None
            
            # If both failed, fallback to template
            if not results.get('claude') and not results.get('gemini'):
                print("⚠️ Both LLM generations failed, falling back to template")
                template_content = self.template_generator.generate_base_template(business_data, include_calendar)
                fallback_prompt = GeneratedPrompt(
                    prompt_text=template_content,
                    business_data=business_data,
                    generation_timestamp=datetime.now().isoformat(),
                    quality_score=0.6,
                    validation_notes=["Generated from template (fallback - LLM not available or failed)"]
                )
                results['template'] = fallback_prompt
        else:
            # Template-only generation
            template_content = self.template_generator.generate_base_template(business_data, include_calendar)
            results['template'] = GeneratedPrompt(
                prompt_text=template_content,
                business_data=business_data,
                generation_timestamp=datetime.now().isoformat(),
                quality_score=0.7,
                validation_notes=["Generated from template only"]
            )
        
        return results
    
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
        
        # Parse service providers
        service_providers = onboarding_json.get("service_providers", [])
        if not isinstance(service_providers, list):
            service_providers = []
        
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
            service_providers=service_providers,
            appointment_duration=onboarding_json.get("appointment_duration", 30),
            custom_fields=onboarding_json.get("custom_fields")
        )
        
        return business_data
    
    def save_prompts_to_output_directory(self, generated_prompts: Dict[str, GeneratedPrompt], tenant_id: str) -> str:
        """
        Save the generated prompts (agentic approach) to the output directory structure.
        
        Args:
            generated_prompts: Dictionary of generated prompt objects (claude, gemini, template)
            tenant_id: Tenant identifier for directory naming
            
        Returns:
            Path to the output directory
        """
        
        # Create output directory structure
        base_dir = "/Users/sandilya/CascadeProjects/receptionist_lovable/prompt_generation"
        output_dir = f"{base_dir}/output_prompts/{tenant_id}"
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save each generated prompt with appropriate filename
        saved_files = []
        combined_metadata = {
            "tenant_id": tenant_id,
            "generation_timestamp": datetime.now().isoformat(),
            "models": {}
        }
        
        for model_name, prompt in generated_prompts.items():
            if prompt is not None:
                # Save prompt file
                if model_name == 'claude':
                    filename = "assistant_claude.txt"
                elif model_name == 'gemini':
                    filename = "assistant_gemini.txt"
                else:
                    filename = f"assistant_{model_name}.txt"
                
                prompt_path = f"{output_dir}/{filename}"
                prompt.save_to_file(prompt_path)
                saved_files.append(prompt_path)
                
                # Add to combined metadata
                combined_metadata[model_name] = {
                    "filename": filename,
                    "business_name": prompt.business_data.business_name if prompt.business_data else "Unknown",
                    "generation_timestamp": prompt.generation_timestamp,
                    "quality_score": prompt.quality_score,
                    "validation_notes": prompt.validation_notes,
                    "model_metadata": getattr(prompt, 'metadata', {}),
                    "scoring_breakdown": getattr(prompt, 'metadata', {}).get('scoring_breakdown', {}) if hasattr(prompt, 'metadata') and prompt.metadata else {}
                }
                
                print(f"✅ {model_name.title()} prompt saved to: {prompt_path}")
        
        # Save combined metadata
        metadata_path = f"{output_dir}/metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(combined_metadata, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Combined metadata saved to: {metadata_path}")
        print(f"📋 Review the generated prompts and copy to production when ready")
        
        return output_dir
    
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
        
        Service Provider format:
        - Available Staff/Service Providers:
        * Name - Role/Specialization
        Email for calendar appointment bookings - provider@email.com
        
        Args:
            input_file_path: Path to the input text file
            
        Returns:
            BusinessData object parsed from the file
        """
        
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"Input file not found: {input_file_path}")
        
        # Read the entire file content for doctor parsing
        with open(input_file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # Parse basic business info
        business_info = {}
        lines = file_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and ':' in line and not line.startswith('*') and not line.startswith('-'):
                key, value = line.split(':', 1)
                business_info[key.strip().lower()] = value.strip()
        
        # Parse service provider information
        service_providers = self._parse_service_providers_from_content(file_content)
        business_info['service_providers'] = service_providers
        
        # Convert to BusinessData using the existing parsing logic
        return self._parse_onboarding_data(business_info)
    
    def _parse_service_providers_from_content(self, file_content: str) -> List[ServiceProviderInfo]:
        """
        Parse service provider information from file content.
        
        Expected format:
        - Available Staff/Service Providers:
        * Name - Role/Specialization
        Email for calendar appointment bookings - provider@email.com
        
        Args:
            file_content: Full content of the input file
            
        Returns:
            List of ServiceProviderInfo objects
        """
        service_providers = []
        lines = file_content.split('\n')
        
        current_provider = None
        current_email = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Look for provider entries starting with * (flexible matching)
            if line.startswith('*') and any(keyword in line.lower() for keyword in ['dr.', 'mr.', 'ms.', 'mrs.', 'stylist', 'consultant', 'therapist']) or (line.startswith('*') and ' - ' in line):
                # Parse provider name and role
                provider_line = line[1:].strip()  # Remove the *
                if ' - ' in provider_line:
                    name_part, role = provider_line.split(' - ', 1)
                    name = name_part.strip()
                    role = role.strip()
                else:
                    name = provider_line.strip()
                    role = "Service Provider"
                
                current_provider = {
                    'name': name,
                    'role': role
                }
            
            # Look for email on the next line
            elif line.startswith('Email for calendar') and current_provider:
                if ' - ' in line:
                    email = line.split(' - ', 1)[1].strip()
                    current_email = email
                    
                    # Create ServiceProviderInfo object
                    provider_info = ServiceProviderInfo(
                        name=current_provider['name'],
                        role=current_provider['role'],
                        email=current_email
                    )
                    
                    # Parse additional info if available in subsequent lines
                    j = i + 1
                    while j < len(lines) and lines[j].strip():
                        next_line = lines[j].strip()
                        if any(qual in next_line for qual in ['MBBS', 'Diploma', 'Certificate', 'Degree', 'Certified']):
                            if not provider_info.qualifications:
                                provider_info.qualifications = next_line
                            else:
                                provider_info.qualifications += f", {next_line}"
                        elif 'Experience' in next_line or any(year in next_line for year in ['2005', '2006', '2007', '2008', '2009', '2010', '2011', '2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024']):
                            if not provider_info.experience:
                                provider_info.experience = next_line
                            else:
                                provider_info.experience += f", {next_line}"
                        elif 'Registration' in next_line or any(char.isdigit() for char in next_line):
                            if not provider_info.registration:
                                provider_info.registration = next_line
                        j += 1
                    
                    service_providers.append(provider_info)
                    current_provider = None
                    current_email = None
        
        return service_providers

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
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--input', required=True, help='Input file containing business data')
    parser.add_argument('--tenant', required=True, help='Tenant name for output directory')
    parser.add_argument('--approach', choices=['template', 'llm', 'data-first'], 
                       default='data-first', help='Approach to use for prompt generation')
    parser.add_argument('--calendar', action='store_true', 
                       help='Include calendar booking functionality in the generated prompt')
    parser.add_argument('--test', action='store_true',
                       help='Run with example data (ignores --input and --tenant)')
    parser.add_argument('--no-llm', action='store_true',
                       help='Skip LLM refinement, use template only')
    parser.add_argument('--model', choices=['claude', 'gemini'], 
                       help='Specific model to use for generation (claude or gemini). If not specified, both models will be used.')
    
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
        
        # Pass raw input text to template generator for CSV preservation
        if hasattr(generator.template_generator, '_set_raw_input_text'):
            generator.template_generator._set_raw_input_text(business_input_text)
        
        print(f"✅ Loaded data for: {business_data.business_name}")
        print(f"   Business Type: {business_data.business_type.value}")
        print(f"   Location: {business_data.location}")
        print(f"   Services: {len(business_data.services)} services listed")
        print()
        
        # Generate prompt (agentic approach)
        use_llm = not args.no_llm
        print(f"🚀 Generating prompts (Agentic approach: {'LLM models' if use_llm else 'template-only'})...")
        
        generated_prompts = generator.generate_agent_prompt(business_data, business_input_text, use_llm_refinement=use_llm, include_calendar=args.calendar, model=args.model)
        
        # Save to output directory
        output_path = generator.save_prompts_to_output_directory(generated_prompts, args.tenant)
        
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
