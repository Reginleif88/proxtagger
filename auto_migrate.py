#!/usr/bin/env python3
"""
Automatic migration helper that runs on startup to safely migrate data
"""

import os
import shutil
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def check_and_migrate():
    """Check if migration is needed and perform it automatically with safety measures"""
    
    # Define file mappings (old path -> new path)
    file_mappings = {
        'config.json': 'data/config.json',
        'conditional_rules.json': 'data/conditional_rules.json',
        'rule_execution_history.json': 'data/rule_execution_history.json'
    }
    
    # Check if any old files exist
    old_files_exist = []
    for old_path in file_mappings.keys():
        if os.path.exists(old_path):
            old_files_exist.append(old_path)
    
    if not old_files_exist:
        # No migration needed
        return {"migrated": False, "reason": "No old files found"}
    
    # Check if this is a Docker environment with volume mount
    # If /app is mounted as a volume, we need to be extra careful
    is_docker = os.path.exists('/.dockerenv')
    
    # Check if the entire /app directory is mounted (old style)
    # This is indicated by certain mount indicators
    whole_app_mounted = False
    if is_docker:
        try:
            # Check if we can write to /app directly (which we shouldn't be able to if just /app/data is mounted)
            test_file = '/app/test_mount_detection'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            whole_app_mounted = True
        except (PermissionError, OSError):
            # This is good - means we can't write to /app root, so only /app/data is mounted
            pass
    
    # Ensure data directory exists
    if not os.path.exists('data'):
        os.makedirs('data')
        logger.info("Created data directory")
    
    # Create a backup directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_before_migration_{timestamp}"
    
    # Only create backup in non-Docker environments or if we can write to the directory
    backup_created = False
    try:
        os.makedirs(backup_dir)
        backup_created = True
        logger.info(f"Created backup directory: {backup_dir}")
    except Exception as e:
        logger.warning(f"Could not create backup directory: {e}")
    
    migrated_files = []
    warnings = []
    
    for old_path, new_path in file_mappings.items():
        if not os.path.exists(old_path):
            continue
            
        # Check if new file already exists
        if os.path.exists(new_path):
            # Compare files to see if they're different
            try:
                with open(old_path, 'r') as f1, open(new_path, 'r') as f2:
                    old_data = json.load(f1)
                    new_data = json.load(f2)
                    
                    if old_data != new_data:
                        warnings.append(f"CONFLICT: Both {old_path} and {new_path} exist with different content!")
                        logger.warning(f"Conflict detected for {old_path}")
                        continue
                    else:
                        logger.info(f"Skipping {old_path} - identical file already exists at {new_path}")
                        continue
            except Exception as e:
                warnings.append(f"Could not compare {old_path} and {new_path}: {e}")
                continue
        
        try:
            # Create backup if possible
            if backup_created:
                shutil.copy2(old_path, os.path.join(backup_dir, old_path))
                logger.info(f"Backed up {old_path}")
            
            # Copy to new location
            shutil.copy2(old_path, new_path)
            logger.info(f"Migrated {old_path} -> {new_path}")
            migrated_files.append(old_path)
            
            # Verify the copy
            with open(old_path, 'r') as f1, open(new_path, 'r') as f2:
                if json.load(f1) == json.load(f2):
                    logger.info(f"Verified {new_path} matches original")
                else:
                    raise Exception("Verification failed - files don't match!")
                    
        except Exception as e:
            logger.error(f"Failed to migrate {old_path}: {e}")
            warnings.append(f"Failed to migrate {old_path}: {e}")
    
    result = {
        "migrated": len(migrated_files) > 0,
        "files_migrated": migrated_files,
        "warnings": warnings,
        "backup_dir": backup_dir if backup_created else None,
        "is_docker": is_docker,
        "whole_app_mounted": whole_app_mounted
    }
    
    if migrated_files and not warnings:
        logger.info("Migration completed successfully!")
        logger.info("Old files have been preserved. You can delete them after verifying the new setup works.")
        
    return result