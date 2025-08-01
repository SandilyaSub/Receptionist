# Automated Prompt Generation System

This module automates the creation of high-quality AI agent prompts for new business onboarding.

## Architecture

### Phase 1: Template + LLM Refinement
- **Input**: Business details from onboarding form
- **Process**: Structured template generation → Claude 3.5 Sonnet refinement
- **Output**: Production-ready system instructions

### Components

1. **template_generator.py** - Creates base prompt structure from business data
2. **llm_refiner.py** - Uses Claude to refine and enhance the template
3. **prompt_validator.py** - Validates output against quality standards
4. **exemplars/** - Reference prompts for few-shot learning

## Usage

```python
from prompt_generation import generate_agent_prompt

business_data = {
    "business_name": "Sreedevi Dental Clinic",
    "business_type": "Healthcare",
    "services": ["Dental consultation", "Teeth cleaning", "Root canal"],
    "location": "Rajahmundry",
    "working_hours": "9 AM - 6 PM",
    "language_preferences": ["Telugu", "English"]
}

prompt = generate_agent_prompt(business_data)
```

## Quality Standards

Generated prompts must include:
- ✅ Consistent Aarohi persona
- ✅ Cultural sensitivity (IST, Indian context)
- ✅ Language matching capabilities
- ✅ Clear operational boundaries
- ✅ Systematic information gathering
- ✅ Professional handoff procedures
