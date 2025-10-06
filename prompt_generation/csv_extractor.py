"""
CSV Extractor for Prompt Generation
Extracts and preserves CSV sections from business input text
"""

import re
from typing import List, Dict, Optional

def extract_csv_sections(text: str) -> str:
    """Extract CSV sections from business input text and return formatted sections."""
    
    csv_sections = []
    
    # Extract specialist/doctor CSV data
    specialist_csv = extract_specialist_csv(text)
    if specialist_csv:
        csv_sections.append("SPECIALIST/DOCTOR INFORMATION:")
        csv_sections.append(specialist_csv)
    
    # Extract escalation/handover CSV data
    escalation_csv = extract_escalation_csv(text)
    if escalation_csv:
        csv_sections.append("ESCALATION CONTACTS:")
        csv_sections.append(escalation_csv)
    
    return "\n\n".join(csv_sections) if csv_sections else ""

def extract_specialist_csv(text: str) -> Optional[str]:
    """Extract specialist/doctor CSV data from text."""
    
    # Look for CSV pattern with Specialization,Name,Email,Working Hours,Days Off
    lines = text.split('\n')
    csv_lines = []
    in_csv_section = False
    
    for line in lines:
        line = line.strip()
        
        # Check if this looks like a CSV header for specialists
        if re.match(r'specialization.*name.*email.*working.*hours.*days.*off', line.lower().replace(',', '').replace(' ', '')):
            in_csv_section = True
            csv_lines.append(line)
            continue
        
        # If we're in CSV section and line has comma-separated values with email pattern
        if in_csv_section and ',' in line and '@' in line:
            csv_lines.append(line)
        elif in_csv_section and line == '':
            # Empty line might end CSV section, but continue to check next line
            continue
        elif in_csv_section and line and ',' not in line:
            # Non-CSV line encountered, end CSV section
            break
    
    return '\n'.join(csv_lines) if csv_lines else None

def extract_escalation_csv(text: str) -> Optional[str]:
    """Extract escalation/handover CSV data from text."""
    
    lines = text.split('\n')
    csv_lines = []
    in_csv_section = False
    
    for line in lines:
        line = line.strip()
        
        # Check if this looks like escalation section
        if 'escalation' in line.lower():
            in_csv_section = True
            continue
        
        # Check if this looks like a CSV header for departments/phones
        if re.match(r'department.*phone', line.lower().replace(',', '').replace(' ', '')):
            in_csv_section = True
            csv_lines.append(line)
            continue
        
        # If we're in CSV section and line has comma-separated values with phone pattern
        if in_csv_section and ',' in line and ('+' in line or re.search(r'\d{10}', line)):
            csv_lines.append(line)
        elif in_csv_section and line == '':
            # Empty line might end CSV section
            continue
        elif in_csv_section and line and ',' not in line and not line.startswith('#'):
            # Non-CSV line encountered, end CSV section
            break
    
    return '\n'.join(csv_lines) if csv_lines else None

def create_specialist_csv_if_missing(text: str) -> str:
    """Create CSV format for specialist info if not already in CSV format."""
    
    # This is a placeholder - would need more sophisticated parsing
    # to extract doctor names, specializations, etc. from free text
    # For now, return empty string if no CSV found
    return ""

def create_escalation_csv_if_missing(text: str) -> str:
    """Create CSV format for escalation info if not already in CSV format."""
    
    # Look for phone numbers and departments in text
    lines = text.split('\n')
    departments = []
    
    for line in lines:
        # Look for patterns like "Emergency: +91..." or "Admin: +91..."
        if ':' in line and ('+' in line or re.search(r'\d{10}', line)):
            parts = line.split(':')
            if len(parts) == 2:
                dept = parts[0].strip()
                phone = parts[1].strip()
                departments.append(f"{dept},{phone}")
    
    if departments:
        return "Department,PhoneNumber\n" + '\n'.join(departments)
    
    return ""
