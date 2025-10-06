#!/usr/bin/env python3
"""
Character Count Scorer

This module provides scoring functionality for prompt character count optimization
based on Live API recommendations (1000-3000 characters optimal range).
"""

import re
import math
from typing import Dict, Tuple


class CharacterCountScorer:
    """Scores prompts based on character count optimization for Live API."""
    
    # Live API recommended character ranges
    OPTIMAL_MIN = 1000
    OPTIMAL_MAX = 3000
    ACCEPTABLE_MIN = 800
    ACCEPTABLE_MAX = 4000
    MAX_SCORE = 3.0  # Updated to 3 points
    
    def __init__(self):
        """Initialize the character count scorer."""
        pass
    
    def count_characters(self, text: str) -> int:
        """
        Count characters in text, excluding excessive whitespace.
        
        Args:
            text: Input text to count
            
        Returns:
            Character count
        """
        if not text:
            return 0
        
        # Normalize whitespace - replace multiple spaces/newlines with single ones
        normalized = re.sub(r'\s+', ' ', text.strip())
        return len(normalized)
    
    def calculate_character_score(self, text: str) -> Dict:
        """
        Calculate character count score using exponential function for precise scoring.
        
        Scoring methodology (3.0 points maximum):
        - Uses exponential decay function for smooth scoring
        - Optimal range (1000-3000): Full 3.0 points
        - Exponential decay outside optimal range
        - 2 decimal precision for all scores
        
        Args:
            text: Prompt text to evaluate
            
        Returns:
            Dictionary with score details
        """
        char_count = self.count_characters(text)
        max_score = self.MAX_SCORE
        
        if self.OPTIMAL_MIN <= char_count <= self.OPTIMAL_MAX:
            # Perfect range - full score
            score = max_score
            category = "optimal"
            details = f"Character count {char_count} is in optimal range ({self.OPTIMAL_MIN}-{self.OPTIMAL_MAX})"
            
        elif char_count < self.OPTIMAL_MIN:
            # Below optimal - exponential decay
            # Distance from optimal minimum
            distance = self.OPTIMAL_MIN - char_count
            # Exponential decay: score = max_score * e^(-distance/decay_factor)
            # Using decay factor of 400 for smooth transition
            decay_factor = 400
            score = max_score * math.exp(-distance / decay_factor)
            category = "below_optimal"
            details = f"Character count {char_count} is below optimal (needs {distance} more chars)"
            
        else:  # char_count > self.OPTIMAL_MAX
            # Above optimal - exponential decay
            # Distance from optimal maximum
            distance = char_count - self.OPTIMAL_MAX
            # Exponential decay with factor of 2000 for gentler penalty on longer prompts
            decay_factor = 2000
            score = max_score * math.exp(-distance / decay_factor)
            category = "above_optimal"
            details = f"Character count {char_count} is above optimal (needs {distance} fewer chars)"
        
        # Round to 2 decimal places as requested
        score = round(score, 2)
        
        return {
            "score": score,
            "max_score": max_score,
            "character_count": char_count,
            "category": category,
            "details": details,
            "optimal_range": f"{self.OPTIMAL_MIN}-{self.OPTIMAL_MAX}",
            "acceptable_range": f"{self.ACCEPTABLE_MIN}-{self.ACCEPTABLE_MAX}"
        }
    
    def get_optimization_suggestions(self, text: str) -> Dict:
        """
        Get suggestions for optimizing character count.
        
        Args:
            text: Prompt text to analyze
            
        Returns:
            Dictionary with optimization suggestions
        """
        char_score = self.calculate_character_score(text)
        char_count = char_score["character_count"]
        suggestions = []
        
        if char_score["category"] == "too_short":
            suggestions.extend([
                "Add more specific examples and sample phrases",
                "Include additional conversation flow details",
                "Expand tool usage rules and guidelines",
                "Add more context about business services",
                "Include more detailed personality and tone instructions"
            ])
            
        elif char_score["category"] == "too_long":
            suggestions.extend([
                "Remove redundant or repetitive instructions",
                "Consolidate similar rules into single bullet points",
                "Shorten verbose explanations while keeping key information",
                "Remove excessive examples if they don't add unique value",
                "Combine related sections to reduce header overhead"
            ])
            
        elif char_score["category"] == "acceptable_low":
            suggestions.extend([
                "Add a few more specific examples",
                "Include additional edge case handling",
                "Expand on cultural context or personality traits"
            ])
            
        elif char_score["category"] == "acceptable_high":
            suggestions.extend([
                "Review for any redundant information",
                "Consolidate similar instructions",
                "Ensure all content adds unique value"
            ])
            
        else:  # optimal
            suggestions.append("Character count is optimal - no changes needed")
        
        return {
            "current_count": char_count,
            "target_range": f"{self.OPTIMAL_MIN}-{self.OPTIMAL_MAX}",
            "suggestions": suggestions,
            "priority": "high" if char_score["category"] in ["too_short", "too_long"] else "low"
        }
    
    def compare_prompts(self, prompt1: str, prompt2: str, labels: Tuple[str, str] = ("Prompt 1", "Prompt 2")) -> Dict:
        """
        Compare character counts of two prompts.
        
        Args:
            prompt1: First prompt text
            prompt2: Second prompt text  
            labels: Labels for the prompts
            
        Returns:
            Comparison results
        """
        score1 = self.calculate_character_score(prompt1)
        score2 = self.calculate_character_score(prompt2)
        
        return {
            labels[0]: {
                "character_count": score1["character_count"],
                "score": score1["score"],
                "category": score1["category"]
            },
            labels[1]: {
                "character_count": score2["character_count"],
                "score": score2["score"],
                "category": score2["category"]
            },
            "winner": labels[0] if score1["score"] > score2["score"] else labels[1] if score2["score"] > score1["score"] else "tie",
            "difference": abs(score1["character_count"] - score2["character_count"])
        }
