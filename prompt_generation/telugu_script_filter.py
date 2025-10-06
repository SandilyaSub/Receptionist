#!/usr/bin/env python3
"""
Telugu Script Filter

This module provides functions to detect and remove Telugu Devanagari script text
while preserving transliterated Telugu (Roman script) text.
"""

import re
import unicodedata

def is_telugu_script(text: str) -> bool:
    """
    Check if text contains Telugu Devanagari script characters.
    
    Args:
        text: String to check
        
    Returns:
        True if text contains Telugu script characters, False otherwise
    """
    if not text:
        return False
    
    # Telugu Unicode range: U+0C00 to U+0C7F
    telugu_pattern = re.compile(r'[\u0C00-\u0C7F]')
    return bool(telugu_pattern.search(text))

def remove_telugu_script_lines(text: str) -> str:
    """
    Remove lines that contain Telugu Devanagari script text.
    
    Args:
        text: Input text with potential Telugu script
        
    Returns:
        Text with Telugu script lines removed
    """
    if not text:
        return text
    
    lines = text.split('\n')
    filtered_lines = []
    
    for line in lines:
        if not is_telugu_script(line):
            filtered_lines.append(line)
        else:
            # Keep the line structure but remove Telugu content
            # Check if line has both Telugu and English/transliterated content
            words = line.split()
            english_words = []
            
            for word in words:
                if not is_telugu_script(word):
                    english_words.append(word)
            
            if english_words:
                # If there are English words, keep them
                filtered_line = ' '.join(english_words)
                # Only add if it's not just punctuation or formatting
                if re.search(r'[a-zA-Z]', filtered_line):
                    filtered_lines.append(filtered_line)
    
    return '\n'.join(filtered_lines)

def replace_telugu_with_transliteration(text: str) -> str:
    """
    Replace common Telugu script phrases with their transliterated equivalents.
    
    Args:
        text: Input text with potential Telugu script
        
    Returns:
        Text with Telugu script replaced by transliterations
    """
    # Common Telugu phrases and their transliterations
    replacements = {
        'నమస్తే': 'Namaste',
        'నమస్కారం': 'Namaskaram',
        'ధన్యవాదాలు': 'Dhanyavadalu',
        'క్షమించండి': 'Kshaminchandi',
        'అపాయింట్‌మెంట్': 'appointment',
        'డాక్టర్': 'doctor',
        'క్లినిక్': 'clinic',
        'సమయం': 'samayam',
        'తేదీ': 'thedi',
        'రోజు': 'roju',
        'ఉదయం': 'udayam',
        'సాయంత్రం': 'sayantram',
        'మధ్యాహ్నం': 'madhyanam',
        'రాత్రి': 'ratri',
        'గారు': 'garu',
        'సార్': 'sir',
        'మేడమ్': 'madam'
    }
    
    result = text
    for telugu, transliteration in replacements.items():
        result = result.replace(telugu, transliteration)
    
    return result

def clean_telugu_script_from_prompt(prompt_text: str) -> str:
    """
    Clean Telugu Devanagari script from prompt while preserving structure.
    
    Args:
        prompt_text: Generated prompt text
        
    Returns:
        Cleaned prompt text with only transliterated Telugu
    """
    if not prompt_text:
        return prompt_text
    
    # First, try to replace common phrases with transliterations
    cleaned_text = replace_telugu_with_transliteration(prompt_text)
    
    # Then remove any remaining Telugu script lines
    cleaned_text = remove_telugu_script_lines(cleaned_text)
    
    # Clean up any empty lines or malformed sections
    lines = cleaned_text.split('\n')
    final_lines = []
    
    for line in lines:
        # Skip empty lines that might have been created by Telugu removal
        if line.strip():
            final_lines.append(line)
        elif final_lines and final_lines[-1].strip():
            # Keep single empty lines for formatting
            final_lines.append(line)
    
    return '\n'.join(final_lines)

def validate_no_telugu_script(text: str) -> tuple[bool, list[str]]:
    """
    Validate that text contains no Telugu Devanagari script.
    
    Args:
        text: Text to validate
        
    Returns:
        Tuple of (is_valid, list_of_telugu_lines)
    """
    if not text:
        return True, []
    
    lines = text.split('\n')
    telugu_lines = []
    
    for i, line in enumerate(lines, 1):
        if is_telugu_script(line):
            telugu_lines.append(f"Line {i}: {line.strip()}")
    
    return len(telugu_lines) == 0, telugu_lines
