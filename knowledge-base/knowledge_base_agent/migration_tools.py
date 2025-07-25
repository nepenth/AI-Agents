#!/usr/bin/env python3
"""
Migration and Deployment Tools for JSON Prompt System

This module provides tools for migrating from the original prompt system
to the JSON-based system, including validation, rollback, and deployment utilities.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .json_prompt_manager import JsonPromptManager
from .json_prompt import JsonPrompt


class MigrationManager:
    """Manages migration from original to JSON prompt system."""
    
    def __init__(self, backup_dir: Optional[Path] = None):
        """Initialize migration manager."""
        self.backup_dir = backup_dir or Path("./backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Migration state file
        self.state_file = self.backup_dir / "migration_state.json"
        self.load_migration_state()
    
    def load_migration_state(self):
        """Load migration state from file."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                self.state = json.load(f)
        else:
            self.state = {
                "migrations": [],
                "current_system": "original",
                "last_migration": None,
                "rollback_available": False
            }
    
    def save_migration_state(self):
        """Save migration state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        return {
            "current_system": self.state["current_system"],
            "last_migration": self.state["last_migration"],
            "rollback_available": self.state["rollback_available"],
            "total_migrations": len(self.state["migrations"]),
            "backup_directory": str(self.backup_dir),
            "available_backups": [
                d.name for d in self.backup_dir.iterdir() 
                if d.is_dir() and d.name.startswith("backup_")
            ]
        }
    
    def validate_json_prompts(self) -> Dict[str, Any]:
        """Validate all JSON prompts in the system."""
        print("🔍 Validating JSON prompt system...")
        
        try:
            manager = JsonPromptManager()
            available_prompts = manager.get_available_prompts()
            
            results = {
                "valid": True,
                "total_prompts": 0,
                "valid_prompts": 0,
                "invalid_prompts": 0,
                "errors": []
            }
            
            for model_type, prompt_ids in available_prompts.items():
                for prompt_id in prompt_ids:
                    results["total_prompts"] += 1
                    
                    try:
                        validation_result = manager.validate_prompt(prompt_id, model_type)
                        
                        if validation_result["valid"]:
                            results["valid_prompts"] += 1
                        else:
                            results["invalid_prompts"] += 1
                            results["valid"] = False
                            results["errors"].extend(validation_result["errors"])
                        
                    except Exception as e:
                        results["invalid_prompts"] += 1
                        results["valid"] = False
                        error_msg = f"Failed to validate {model_type}:{prompt_id}: {e}"
                        results["errors"].append(error_msg)
            
            print(f"📊 Validation Results:")
            print(f"   Total prompts: {results['total_prompts']}")
            print(f"   Valid prompts: {results['valid_prompts']}")
            print(f"   Invalid prompts: {results['invalid_prompts']}")
            
            if results["valid"]:
                print("✅ All prompts are valid")
            else:
                print("❌ Some prompts have validation errors")
            
            return results
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Failed to initialize JSON prompt system: {e}",
                "total_prompts": 0,
                "valid_prompts": 0,
                "invalid_prompts": 0,
                "errors": [str(e)]
            }


class DeploymentManager:
    """Manages deployment of JSON prompt configurations."""
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize deployment manager."""
        self.prompts_dir = prompts_dir or Path("knowledge_base_agent/prompts_json")
    
    def validate_deployment(self) -> Dict[str, Any]:
        """Validate the current deployment."""
        print("🔍 Validating deployment...")
        
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": {}
        }
        
        # Check if prompts directory exists
        if not self.prompts_dir.exists():
            results["valid"] = False
            results["errors"].append(f"Prompts directory not found: {self.prompts_dir}")
            return results
        
        results["checks"]["prompts_directory"] = "✅ Found"
        
        # Check config file
        config_file = self.prompts_dir / "config.json"
        if not config_file.exists():
            results["valid"] = False
            results["errors"].append(f"Config file not found: {config_file}")
        else:
            results["checks"]["config_file"] = "✅ Found"
        
        # Check environment configuration
        use_json_prompts = os.getenv('USE_JSON_PROMPTS', 'true').lower() == 'true'
        if use_json_prompts:
            results["checks"]["environment"] = "✅ JSON prompts enabled"
        else:
            results["warnings"].append("JSON prompts not enabled in environment")
            results["checks"]["environment"] = "⚠️  JSON prompts disabled"
        
        return results
