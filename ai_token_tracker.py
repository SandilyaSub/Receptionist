"""
AI Token Tracker for tracking token usage across all AI operations

This module provides functionality to accumulate token usage from:
1. Gemini Live API (conversation)
2. Transcript analysis (generate_content)
3. WhatsApp message generation (generate_content)
"""

import logging
import json
from typing import Dict, Any, Optional
from supabase_client import get_supabase_client


class CallTokenAccumulator:
    """
    Accumulates AI token usage for a single call and provides batch update to database
    """
    
    def __init__(self, call_sid: str, logger: Optional[logging.Logger] = None):
        """
        Initialize token accumulator for a specific call
        
        Args:
            call_sid: The call SID to track tokens for
            logger: Optional logger instance
        """
        self.call_sid = call_sid
        self.logger = logger or logging.getLogger(__name__)
        self.tokens = {}
        
    def add_conversation_tokens(self, usage_metadata, model: str):
        """
        Add token usage from Gemini Live API conversation
        
        Args:
            usage_metadata: Usage metadata from Gemini Live API message
            model: Model name used (e.g., "gemini-2.0-flash-exp")
        """
        try:
            if not usage_metadata:
                return
                
            # Extract tokens from Live API usage metadata
            conversation_tokens = {
                "model": model,
                "total_tokens": getattr(usage_metadata, 'total_token_count', 0),
                "input_tokens": getattr(usage_metadata, 'input_token_count', 0),
                "output_tokens": getattr(usage_metadata, 'output_token_count', 0)
            }
            
            # Add response breakdown if available
            if hasattr(usage_metadata, 'response_tokens_details'):
                conversation_tokens["response_breakdown"] = []
                for detail in usage_metadata.response_tokens_details:
                    conversation_tokens["response_breakdown"].append({
                        "modality": str(detail.modality) if hasattr(detail, 'modality') else "unknown",
                        "count": getattr(detail, 'token_count', 0)
                    })
            
            # Accumulate conversation tokens (sum if multiple updates)
            if "conversation" not in self.tokens:
                self.tokens["conversation"] = conversation_tokens
            else:
                # Sum up tokens from multiple conversation updates
                existing = self.tokens["conversation"]
                existing["total_tokens"] += conversation_tokens["total_tokens"]
                existing["input_tokens"] += conversation_tokens["input_tokens"]
                existing["output_tokens"] += conversation_tokens["output_tokens"]
                
            self.logger.info(f"Added conversation tokens for call {self.call_sid}: {conversation_tokens['total_tokens']} total")
            
        except Exception as e:
            self.logger.warning(f"Failed to add conversation tokens for call {self.call_sid}: {str(e)}")
    
    def add_analysis_tokens(self, usage_metadata, model: str):
        """
        Add token usage from transcript analysis
        
        Args:
            usage_metadata: Usage metadata from generate_content response
            model: Model name used (e.g., "gemini-2.5-flash")
        """
        try:
            if not usage_metadata:
                return
                
            # Extract tokens from generate_content usage metadata
            analysis_tokens = {
                "model": model,
                "total_tokens": getattr(usage_metadata, 'total_token_count', 0),
                "prompt_tokens": getattr(usage_metadata, 'prompt_token_count', 0),
                "candidates_tokens": getattr(usage_metadata, 'candidates_token_count', 0),
                "thoughts_tokens": getattr(usage_metadata, 'thoughts_token_count', 0)
            }
            
            self.tokens["transcript_analysis"] = analysis_tokens
            self.logger.info(f"Added analysis tokens for call {self.call_sid}: {analysis_tokens['total_tokens']} total")
            
        except Exception as e:
            self.logger.warning(f"Failed to add analysis tokens for call {self.call_sid}: {str(e)}")
    
    def add_whatsapp_tokens(self, usage_metadata, model: str):
        """
        Add token usage from WhatsApp message generation
        
        Args:
            usage_metadata: Usage metadata from generate_content response
            model: Model name used (e.g., "gemini-2.5-flash")
        """
        try:
            if not usage_metadata:
                return
                
            # Extract tokens from generate_content usage metadata
            whatsapp_tokens = {
                "model": model,
                "total_tokens": getattr(usage_metadata, 'total_token_count', 0),
                "prompt_tokens": getattr(usage_metadata, 'prompt_token_count', 0),
                "candidates_tokens": getattr(usage_metadata, 'candidates_token_count', 0),
                "thoughts_tokens": getattr(usage_metadata, 'thoughts_token_count', 0)
            }
            
            self.tokens["whatsapp_generation"] = whatsapp_tokens
            self.logger.info(f"Added WhatsApp tokens for call {self.call_sid}: {whatsapp_tokens['total_tokens']} total")
            
        except Exception as e:
            self.logger.warning(f"Failed to add WhatsApp tokens for call {self.call_sid}: {str(e)}")
    
    def get_total_summary(self) -> Dict[str, Any]:
        """
        Get the complete token usage summary for this call
        
        Returns:
            Dictionary with all token usage data and totals
        """
        # Calculate total tokens across all operations
        total_tokens = 0
        for operation_data in self.tokens.values():
            total_tokens += operation_data.get("total_tokens", 0)
        
        # Create summary with total
        summary = dict(self.tokens)
        summary["total_tokens_all_operations"] = total_tokens
        
        return summary
    
    async def save_to_database(self) -> bool:
        """
        Save accumulated token data to call_details table in Supabase
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            if not self.tokens:
                self.logger.info(f"No token data to save for call {self.call_sid}")
                return True
                
            # Get token summary
            token_summary = self.get_total_summary()
            
            # Update call_details table
            supabase = get_supabase_client()
            response = supabase.table("call_details")\
                .update({"ai_token_usage": token_summary})\
                .eq("call_sid", self.call_sid)\
                .execute()
            
            if response.data:
                self.logger.info(f"Successfully saved token data for call {self.call_sid}: {token_summary['total_tokens_all_operations']} total tokens")
                return True
            else:
                self.logger.warning(f"No rows updated when saving token data for call {self.call_sid}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to save token data for call {self.call_sid}: {str(e)}")
            return False
    
    def get_token_count_summary(self) -> str:
        """
        Get a human-readable summary of token usage
        
        Returns:
            String summary of token usage
        """
        if not self.tokens:
            return f"No token data for call {self.call_sid}"
            
        summary_parts = []
        total = 0
        
        for operation, data in self.tokens.items():
            tokens = data.get("total_tokens", 0)
            model = data.get("model", "unknown")
            summary_parts.append(f"{operation}: {tokens} tokens ({model})")
            total += tokens
            
        summary_parts.append(f"Total: {total} tokens")
        
        return f"Call {self.call_sid} - " + ", ".join(summary_parts)
