#!/usr/bin/env python3
"""
Standalone Prompt Evaluator

This script evaluates existing prompts and updates their metadata.json files
without requiring LLM generation. It can re-score prompts using the latest
scoring methodology and update metadata files in place.

Usage:
    python3 prompt_evaluator.py --tenant <tenant_name>
    python3 prompt_evaluator.py --directory <output_directory>
    python3 prompt_evaluator.py --all
"""

import os
import json
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import glob

# Import the scoring functions from existing refiners
from llm_refiner import ClaudePromptRefiner
from gemini_refiner import GeminiPromptRefiner


class PromptEvaluator:
    """Standalone evaluator for existing prompts."""
    
    def __init__(self):
        self.claude_refiner = ClaudePromptRefiner()
        self.gemini_refiner = GeminiPromptRefiner()
    
    def load_business_input(self, tenant_name: str) -> str:
        """Load business input data for a tenant."""
        input_file = f"input_files/{tenant_name}.txt"
        if os.path.exists(input_file):
            with open(input_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def evaluate_prompt_file(self, prompt_file_path: str, business_input: str, model_type: str) -> Dict:
        """Evaluate a single prompt file and return scoring breakdown."""
        if not os.path.exists(prompt_file_path):
            return {}
        
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
        
        if model_type.lower() == 'claude':
            return self.claude_refiner._calculate_quality_score(prompt_content, business_input)
        elif model_type.lower() == 'gemini':
            return self.gemini_refiner._calculate_quality_score(prompt_content, business_input)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    def update_metadata_file(self, metadata_path: str, tenant_name: str) -> Dict:
        """Update metadata file with new scoring for all models."""
        if not os.path.exists(metadata_path):
            print(f"❌ Metadata file not found: {metadata_path}")
            return {}
        
        # Load existing metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Load business input
        business_input = self.load_business_input(tenant_name)
        
        # Get directory containing the metadata file
        output_dir = os.path.dirname(metadata_path)
        
        # Track updates
        updates = {}
        
        # Check for Claude prompt
        claude_file = os.path.join(output_dir, "assistant_claude.txt")
        if os.path.exists(claude_file):
            print(f"📊 Evaluating Claude prompt...")
            claude_scoring = self.evaluate_prompt_file(claude_file, business_input, 'claude')
            
            if 'claude' not in metadata:
                metadata['claude'] = {}
            
            # Update Claude metadata
            metadata['claude'].update({
                "quality_score": claude_scoring.get("quality_score", 0.0),
                "scoring_breakdown": claude_scoring.get("breakdown", {}),
                "last_evaluated": datetime.now().isoformat()
            })
            
            # Also update model_metadata if it exists
            if "model_metadata" in metadata['claude']:
                metadata['claude']["model_metadata"]["scoring_breakdown"] = claude_scoring.get("breakdown", {})
            
            updates['claude'] = claude_scoring.get("quality_score", 0.0)
        
        # Check for Gemini prompt
        gemini_file = os.path.join(output_dir, "assistant_gemini.txt")
        if os.path.exists(gemini_file):
            print(f"🧠 Evaluating Gemini prompt...")
            gemini_scoring = self.evaluate_prompt_file(gemini_file, business_input, 'gemini')
            
            if 'gemini' not in metadata:
                metadata['gemini'] = {}
            
            # Update Gemini metadata
            metadata['gemini'].update({
                "quality_score": gemini_scoring.get("quality_score", 0.0),
                "scoring_breakdown": gemini_scoring.get("breakdown", {}),
                "last_evaluated": datetime.now().isoformat()
            })
            
            # Also update model_metadata if it exists
            if "model_metadata" in metadata['gemini']:
                metadata['gemini']["model_metadata"]["scoring_breakdown"] = gemini_scoring.get("breakdown", {})
            
            updates['gemini'] = gemini_scoring.get("quality_score", 0.0)
        
        # Update global timestamp
        metadata['last_evaluation'] = datetime.now().isoformat()
        
        # Save updated metadata
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return updates
    
    def evaluate_tenant(self, tenant_name: str) -> bool:
        """Evaluate all prompts for a specific tenant."""
        output_dir = f"output_prompts/{tenant_name}"
        metadata_path = os.path.join(output_dir, "metadata.json")
        
        if not os.path.exists(metadata_path):
            print(f"❌ No metadata found for tenant: {tenant_name}")
            return False
        
        print(f"🔍 Evaluating tenant: {tenant_name}")
        updates = self.update_metadata_file(metadata_path, tenant_name)
        
        if updates:
            print(f"✅ Updated scores for {tenant_name}:")
            for model, score in updates.items():
                print(f"   {model.title()}: {score:.3f}")
            return True
        else:
            print(f"⚠️  No prompts found to evaluate for {tenant_name}")
            return False
    
    def evaluate_directory(self, directory_path: str) -> bool:
        """Evaluate prompts in a specific directory."""
        metadata_path = os.path.join(directory_path, "metadata.json")
        
        if not os.path.exists(metadata_path):
            print(f"❌ No metadata found in directory: {directory_path}")
            return False
        
        # Extract tenant name from directory
        tenant_name = os.path.basename(directory_path)
        
        print(f"🔍 Evaluating directory: {directory_path}")
        updates = self.update_metadata_file(metadata_path, tenant_name)
        
        if updates:
            print(f"✅ Updated scores:")
            for model, score in updates.items():
                print(f"   {model.title()}: {score:.3f}")
            return True
        else:
            print(f"⚠️  No prompts found to evaluate in {directory_path}")
            return False
    
    def evaluate_all(self) -> int:
        """Evaluate all tenants in the output_prompts directory."""
        output_base = "output_prompts"
        
        if not os.path.exists(output_base):
            print(f"❌ Output directory not found: {output_base}")
            return 0
        
        tenant_dirs = [d for d in os.listdir(output_base) 
                      if os.path.isdir(os.path.join(output_base, d))]
        
        if not tenant_dirs:
            print(f"❌ No tenant directories found in {output_base}")
            return 0
        
        print(f"🚀 Evaluating all {len(tenant_dirs)} tenants...")
        
        success_count = 0
        for tenant_name in sorted(tenant_dirs):
            try:
                if self.evaluate_tenant(tenant_name):
                    success_count += 1
                print()  # Add spacing between tenants
            except Exception as e:
                print(f"❌ Error evaluating {tenant_name}: {e}")
        
        print(f"🎉 Evaluation complete! Successfully updated {success_count}/{len(tenant_dirs)} tenants.")
        return success_count


def main():
    parser = argparse.ArgumentParser(description="Evaluate existing prompts and update metadata")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tenant", "-t", help="Evaluate specific tenant")
    group.add_argument("--directory", "-d", help="Evaluate specific directory")
    group.add_argument("--all", "-a", action="store_true", help="Evaluate all tenants")
    
    args = parser.parse_args()
    
    evaluator = PromptEvaluator()
    
    try:
        if args.tenant:
            success = evaluator.evaluate_tenant(args.tenant)
            exit(0 if success else 1)
        
        elif args.directory:
            success = evaluator.evaluate_directory(args.directory)
            exit(0 if success else 1)
        
        elif args.all:
            success_count = evaluator.evaluate_all()
            exit(0 if success_count > 0 else 1)
    
    except KeyboardInterrupt:
        print("\n⚠️  Evaluation interrupted by user")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
