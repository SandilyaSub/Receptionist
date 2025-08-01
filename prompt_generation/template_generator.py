"""
Template Generator for AI Agent Prompts

Creates structured base prompts from business data using proven patterns
from exemplar prompts (happy_endings, joy_invite, gsl_college).
"""

from typing import Dict, List
from business_schema import BusinessData, BusinessType, LanguageCode

class PromptTemplateGenerator:
    """Generates structured prompt templates from business data."""
    
    def __init__(self):
        self.common_behavioral_framework = self._load_common_behaviors()
    
    def _load_common_behaviors(self) -> Dict[str, str]:
        """Define common behavioral instructions for all agents."""
        return {
            "core_identity": """* You are Aarohi, a warm and professional receptionist for {business_name} in {location}
* Speak with a natural Indian English accent and tone
* Be extremely courteous, friendly, and enthusiastic in all interactions
* Use warm greetings like "Namaste" or "Hello" and polite expressions throughout conversations
* Maintain professional yet personable communication at all times""",
            
            "language_adaptation": """LANGUAGE ADAPTATION:
* CRITICAL - Always respond in the same language the caller is speaking in
* If they speak in Hindi, respond in Hindi
* If they speak in English, respond in English
* If they speak in regional languages ({regional_languages}), respond in the same language
* Match their level of formality and cultural expressions
* Use appropriate honorifics (ji, sahib, madam, sir)""",
            
            "operational_boundaries": """OPERATIONAL BOUNDARIES:
* You can ONLY discuss services and information related to {business_name}
* You cannot process payments, confirm bookings, or access internal systems
* For any questions outside {business_type} services, respond: "Sorry, I do not have information about this at the moment"
* Working hours: {working_hours} (Indian Standard Time). All timing references in the conversation are in IST""",
            
            "timezone_requirements": """CRITICAL TIMING REQUIREMENTS:
* ALL conversations happen in Indian Standard Time (IST) ONLY
* NEVER ask customers about their timezone - assume IST
* When customers mention ANY time, treat it as IST
* Always respond with IST times and explicitly mention "IST" in your responses
* Current location: {location}, India - all operations are in IST""",
            
            "information_gathering": """INFORMATION GATHERING: For all inquiries, collect these details systematically:
1. Customer name and phone number
2. Specific service/product requirements
3. Preferred timing or urgency
4. Any special requirements or preferences
5. Contact preferences for follow-up""",
            
            "handoff_process": """PROCESS COMPLETION:
* After gathering all customer details thoroughly
* Confirm all information with the customer
* Inform: "Thank you for choosing {business_name}! Someone from our team will reach out to you shortly with further details. You'll also receive a message with our contact information for any clarifications."
* For urgent matters, emphasize: "For immediate assistance, please call our main number: {phone_number}""",
            
            "limitations": """IMPORTANT LIMITATIONS:
* You cannot access existing customer data or booking systems
* You cannot confirm, modify, or cancel existing bookings
* You cannot process payments or provide payment links
* Always direct final confirmations and transactions to the team
* Stay within the scope of {business_type} services only"""
        }
    
    def generate_base_template(self, business_data: BusinessData) -> str:
        """Generate a structured base template from business data."""
        
        # Prepare template variables
        template_vars = {
            "business_name": business_data.business_name,
            "location": business_data.location,
            "business_type": business_data.business_type.value.replace("_", " ").title(),
            "working_hours": business_data.working_hours,
            "phone_number": business_data.phone_number,
            "regional_languages": ", ".join([lang.value.title() for lang in business_data.supported_languages if lang != LanguageCode.ENGLISH]),
            "services_list": self._format_services_list(business_data.services),
            "greeting_message": self._generate_greeting(business_data)
        }
        
        # Build the template sections
        sections = []
        
        # Core Identity
        sections.append(self.common_behavioral_framework["core_identity"].format(**template_vars))
        
        # Language Adaptation
        if len(business_data.supported_languages) > 1:
            sections.append(self.common_behavioral_framework["language_adaptation"].format(**template_vars))
        
        # Operational Boundaries
        sections.append(self.common_behavioral_framework["operational_boundaries"].format(**template_vars))
        
        # Business-Specific Knowledge
        sections.append(self._generate_business_knowledge_section(business_data))
        
        # Timezone Requirements
        sections.append(self.common_behavioral_framework["timezone_requirements"].format(**template_vars))
        
        # Information Gathering
        sections.append(self._generate_info_gathering_section(business_data))
        
        # Business-Specific Process
        sections.append(self._generate_business_process_section(business_data))
        
        # Handoff Process
        sections.append(self.common_behavioral_framework["handoff_process"].format(**template_vars))
        
        # Limitations
        sections.append(self.common_behavioral_framework["limitations"].format(**template_vars))
        
        # Sample Interaction
        sections.append(f'SAMPLE INTERACTION FLOW: "{template_vars["greeting_message"]}"')
        sections.append("[Gather requirements systematically, provide information, collect details, conclude with team follow-up information]")
        
        sections.append("Remember to be patient, helpful, and maintain enthusiasm throughout every interaction while staying strictly within these operational guidelines.")
        
        return "\n\n".join(sections)
    
    def _format_services_list(self, services: List[str]) -> str:
        """Format the services list for the prompt."""
        if not services:
            return "General services"
        
        formatted_services = []
        for service in services:
            formatted_services.append(f"* {service}")
        
        return "\n".join(formatted_services)
    
    def _generate_greeting(self, business_data: BusinessData) -> str:
        """Generate an appropriate greeting based on business type and language."""
        if business_data.welcome_message:
            return f"Namaste! {business_data.welcome_message} I'm Aarohi. How may I help you today?"
        
        # Default greeting based on business type
        business_type_greetings = {
            BusinessType.HEALTHCARE: f"Namaste! Welcome to {business_data.business_name}. I'm Aarohi, and I'm here to help you with your healthcare needs. How may I assist you today?",
            BusinessType.FOOD_BEVERAGE: f"Namaste! Welcome to {business_data.business_name}! I'm Aarohi. How may I help you today?",
            BusinessType.EDUCATION: f"Namaste! You've reached {business_data.business_name}. I'm Aarohi, and I'm here to help you with your educational inquiries. How may I assist you today?",
            BusinessType.BEAUTY_WELLNESS: f"Namaste! Welcome to {business_data.business_name}. I'm Aarohi, and I'm here to help you with your beauty and wellness needs. How may I assist you today?"
        }
        
        return business_type_greetings.get(
            business_data.business_type,
            f"Namaste! Welcome to {business_data.business_name}. I'm Aarohi. How may I help you today?"
        )
    
    def _generate_business_knowledge_section(self, business_data: BusinessData) -> str:
        """Generate business-specific knowledge section."""
        knowledge_section = f"SERVICES KNOWLEDGE: You have access to information about {business_data.business_name}'s services:\n"
        knowledge_section += self._format_services_list(business_data.services)
        
        if business_data.business_description:
            knowledge_section += f"\n\nBUSINESS OVERVIEW:\n{business_data.business_description}"
        
        if business_data.pricing_info:
            knowledge_section += f"\n\nPRICING INFORMATION:\n"
            for item, price in business_data.pricing_info.items():
                knowledge_section += f"* {item}: {price}\n"
        
        return knowledge_section
    
    def _generate_info_gathering_section(self, business_data: BusinessData) -> str:
        """Generate business-specific information gathering requirements."""
        base_section = self.common_behavioral_framework["information_gathering"]
        
        # Add business-specific requirements
        if business_data.business_type == BusinessType.HEALTHCARE:
            base_section += """
HEALTHCARE-SPECIFIC INFORMATION:
6. Nature of health concern or routine check-up
7. Preferred doctor (if any)
8. Insurance information (if applicable)
9. Previous visit history (if mentioned)
10. Urgency level of the consultation"""
        
        elif business_data.business_type == BusinessType.FOOD_BEVERAGE:
            base_section += """
FOOD SERVICE-SPECIFIC INFORMATION:
6. Dietary preferences or restrictions
7. Quantity required
8. Delivery or pickup preference
9. Special occasion details (if applicable)
10. Preferred delivery time"""
        
        elif business_data.business_type == BusinessType.EDUCATION:
            base_section += """
EDUCATION-SPECIFIC INFORMATION:
6. Course or program of interest
7. Educational background
8. Age group or grade level
9. Learning objectives
10. Preferred class timings"""
        
        if business_data.appointment_required:
            base_section += "\n\nAPPOINTMENT REQUIREMENTS:\n* All services require advance appointment booking\n* Emphasize the importance of scheduling ahead"
        
        return base_section
    
    def _generate_business_process_section(self, business_data: BusinessData) -> str:
        """Generate business-specific process instructions."""
        process_section = ""
        
        if business_data.appointment_required:
            process_section += """APPOINTMENT BOOKING PROCESS:
* All services require prior appointment
* Collect preferred date and time from customer
* Inform about confirmation process through team follow-up
* For urgent cases, emphasize calling the main number directly

"""
        
        if business_data.business_type == BusinessType.HEALTHCARE:
            process_section += """HEALTHCARE-SPECIFIC PROCESS:
* For emergency cases, direct to call main number immediately
* For routine consultations, follow standard appointment booking
* Always ask about current symptoms or health concerns
* Maintain patient confidentiality and professionalism

"""
        
        if business_data.special_instructions:
            process_section += f"SPECIAL INSTRUCTIONS:\n{business_data.special_instructions}\n\n"
        
        return process_section.strip()

# Example usage
if __name__ == "__main__":
    from business_schema import EXAMPLE_BUSINESS_DATA
    
    generator = PromptTemplateGenerator()
    template = generator.generate_base_template(EXAMPLE_BUSINESS_DATA)
    
    print("Generated Template:")
    print("=" * 50)
    print(template)
