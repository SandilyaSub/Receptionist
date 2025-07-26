"""
Language Utilities for Gemini Live API
Provides BCP-47 language code mapping for multi-tenant greeting system.
"""

def map_language_to_bcp47_code(language: str) -> str:
    """Map human language names to Gemini Live API BCP-47 codes (case-insensitive).
    
    Args:
        language: Language name in any case format
        
    Returns:
        BCP-47 language code supported by Gemini Live API
        
    Reference:
        https://ai.google.dev/gemini-api/docs/live-guide#supported-languages
    """
    if not language:
        return 'en-US'  # Default to English (US)
    
    # Convert to lowercase and strip whitespace for consistent mapping
    normalized = language.lower().strip()
    
    # Map human language names and variations to official Gemini Live API BCP-47 codes
    # Based on: https://ai.google.dev/gemini-api/docs/live-guide#supported-languages
    language_to_bcp47 = {
        # English variations
        'english': 'en-US',
        'en': 'en-US',
        'eng': 'en-US',
        'english (us)': 'en-US',
        'english (uk)': 'en-GB',
        'english (australia)': 'en-AU',
        'english (india)': 'en-IN',
        'en-us': 'en-US',
        'en-gb': 'en-GB',
        'en-au': 'en-AU',
        'en-in': 'en-IN',
        
        # Hindi
        'hindi': 'hi-IN',
        'hi': 'hi-IN',
        'hin': 'hi-IN',
        'hindi (india)': 'hi-IN',
        'hi-in': 'hi-IN',
        
        # Telugu
        'telugu': 'te-IN',
        'te': 'te-IN',
        'tel': 'te-IN',
        'telugu (india)': 'te-IN',
        'te-in': 'te-IN',
        
        # Tamil
        'tamil': 'ta-IN',
        'ta': 'ta-IN',
        'tam': 'ta-IN',
        'tamil (india)': 'ta-IN',
        'ta-in': 'ta-IN',
        
        # Bengali
        'bengali': 'bn-IN',
        'bn': 'bn-IN',
        'ben': 'bn-IN',
        'bengali (india)': 'bn-IN',
        'bn-in': 'bn-IN',
        
        # Marathi
        'marathi': 'mr-IN',
        'mr': 'mr-IN',
        'mar': 'mr-IN',
        'marathi (india)': 'mr-IN',
        'mr-in': 'mr-IN',
        
        # Gujarati
        'gujarati': 'gu-IN',
        'gu': 'gu-IN',
        'guj': 'gu-IN',
        'gujarati (india)': 'gu-IN',
        'gu-in': 'gu-IN',
        
        # Kannada
        'kannada': 'kn-IN',
        'kn': 'kn-IN',
        'kan': 'kn-IN',
        'kannada (india)': 'kn-IN',
        'kn-in': 'kn-IN',
        
        # Malayalam
        'malayalam': 'ml-IN',
        'ml': 'ml-IN',
        'mal': 'ml-IN',
        'malayalam (india)': 'ml-IN',
        'ml-in': 'ml-IN',
        
        # Spanish
        'spanish': 'es-ES',
        'es': 'es-ES',
        'esp': 'es-ES',
        'spanish (spain)': 'es-ES',
        'spanish (us)': 'es-US',
        'es-es': 'es-ES',
        'es-us': 'es-US',
        
        # French
        'french': 'fr-FR',
        'fr': 'fr-FR',
        'fre': 'fr-FR',
        'french (france)': 'fr-FR',
        'french (canada)': 'fr-CA',
        'fr-fr': 'fr-FR',
        'fr-ca': 'fr-CA',
        
        # German
        'german': 'de-DE',
        'de': 'de-DE',
        'ger': 'de-DE',
        'german (germany)': 'de-DE',
        'de-de': 'de-DE',
        
        # Portuguese
        'portuguese': 'pt-BR',
        'pt': 'pt-BR',
        'por': 'pt-BR',
        'portuguese (brazil)': 'pt-BR',
        'pt-br': 'pt-BR',
        
        # Arabic
        'arabic': 'ar-XA',
        'ar': 'ar-XA',
        'ara': 'ar-XA',
        'arabic (generic)': 'ar-XA',
        'ar-xa': 'ar-XA',
        
        # Indonesian
        'indonesian': 'id-ID',
        'id': 'id-ID',
        'ind': 'id-ID',
        'indonesian (indonesia)': 'id-ID',
        'id-id': 'id-ID',
        
        # Italian
        'italian': 'it-IT',
        'it': 'it-IT',
        'ita': 'it-IT',
        'italian (italy)': 'it-IT',
        'it-it': 'it-IT',
        
        # Japanese
        'japanese': 'ja-JP',
        'ja': 'ja-JP',
        'jpn': 'ja-JP',
        'japanese (japan)': 'ja-JP',
        'ja-jp': 'ja-JP',
        
        # Korean
        'korean': 'ko-KR',
        'ko': 'ko-KR',
        'kor': 'ko-KR',
        'korean (south korea)': 'ko-KR',
        'ko-kr': 'ko-KR',
        
        # Turkish
        'turkish': 'tr-TR',
        'tr': 'tr-TR',
        'tur': 'tr-TR',
        'turkish (turkey)': 'tr-TR',
        'tr-tr': 'tr-TR',
        
        # Vietnamese
        'vietnamese': 'vi-VN',
        'vi': 'vi-VN',
        'vie': 'vi-VN',
        'vietnamese (vietnam)': 'vi-VN',
        'vi-vn': 'vi-VN',
        
        # Dutch
        'dutch': 'nl-NL',
        'nl': 'nl-NL',
        'dut': 'nl-NL',
        'dutch (netherlands)': 'nl-NL',
        'nl-nl': 'nl-NL',
        
        # Mandarin Chinese
        'chinese': 'cmn-CN',
        'mandarin': 'cmn-CN',
        'cmn': 'cmn-CN',
        'mandarin chinese': 'cmn-CN',
        'mandarin chinese (china)': 'cmn-CN',
        'cmn-cn': 'cmn-CN',
        
        # Polish
        'polish': 'pl-PL',
        'pl': 'pl-PL',
        'pol': 'pl-PL',
        'polish (poland)': 'pl-PL',
        'pl-pl': 'pl-PL',
        
        # Russian
        'russian': 'ru-RU',
        'ru': 'ru-RU',
        'rus': 'ru-RU',
        'russian (russia)': 'ru-RU',
        'ru-ru': 'ru-RU',
        
        # Thai
        'thai': 'th-TH',
        'th': 'th-TH',
        'tha': 'th-TH',
        'thai (thailand)': 'th-TH',
        'th-th': 'th-TH'
    }
    
    return language_to_bcp47.get(normalized, 'en-US')  # Default to English (US) if not found


def get_supported_languages():
    """Get list of all supported Gemini Live API language codes.
    
    Returns:
        list: All supported BCP-47 language codes
    """
    return [
        'de-DE', 'en-AU', 'en-GB', 'en-IN', 'en-US', 'es-US', 'fr-FR', 
        'hi-IN', 'pt-BR', 'ar-XA', 'es-ES', 'fr-CA', 'id-ID', 'it-IT', 
        'ja-JP', 'tr-TR', 'vi-VN', 'bn-IN', 'gu-IN', 'kn-IN', 'mr-IN', 
        'ml-IN', 'ta-IN', 'te-IN', 'nl-NL', 'ko-KR', 'cmn-CN', 'pl-PL', 
        'ru-RU', 'th-TH'
    ]


def validate_bcp47_code(language_code: str) -> bool:
    """Validate if a BCP-47 code is supported by Gemini Live API.
    
    Args:
        language_code: BCP-47 language code to validate
        
    Returns:
        bool: True if supported, False otherwise
    """
    return language_code in get_supported_languages()
