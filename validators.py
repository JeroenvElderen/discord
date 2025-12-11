"""
Validation utilities for Discord bot configuration.
Ensures tokens and configuration values are valid before bot startup.
"""
import os
import re
import sys
from typing import Optional

# Constants for validation
MIN_TOKEN_LENGTH = 50  # Minimum expected length for a Discord bot token
MIN_VALID_SNOWFLAKE = 41771983423143936  # Minimum Discord Snowflake (~2015)
MAX_VALID_SNOWFLAKE = 9223372036854775807  # Maximum 64-bit signed integer


def validate_discord_token(token: Optional[str]) -> tuple[bool, str]:
    """
    Validate Discord bot token format and existence.
    
    Args:
        token: The Discord bot token to validate
        
    Returns:
        A tuple of (is_valid, error_message)
        - is_valid: True if token is valid, False otherwise
        - error_message: Empty string if valid, error description if invalid
    """
    if token is None:
        return False, "DISCORD_TOKEN environment variable is not set"
    
    if not token or token.strip() == "":
        return False, "DISCORD_TOKEN is empty"
    
    if token == "your_bot_token_here":
        return False, "DISCORD_TOKEN is still set to placeholder value. Please set your actual bot token"
    
    # Discord tokens have a specific format:
    # - Part 1: Base64 encoded user ID
    # - Part 2: Timestamp
    # - Part 3: HMAC signature
    # They're separated by dots and should be at least MIN_TOKEN_LENGTH characters
    if len(token) < MIN_TOKEN_LENGTH:
        return False, f"DISCORD_TOKEN appears to be too short (expected at least {MIN_TOKEN_LENGTH} characters)"
    
    # Basic format check: should contain at least two dots (three parts)
    if token.count('.') < 2:
        return False, "DISCORD_TOKEN has invalid format (expected format: xxx.yyy.zzz)"
    
    # Check for common whitespace issues
    if token != token.strip():
        return False, "DISCORD_TOKEN contains leading or trailing whitespace"
    
    return True, ""


def validate_snowflake_id(snowflake_id: int, name: str) -> tuple[bool, str]:
    """
    Validate Discord Snowflake ID (used for channels, roles, users, etc.).
    
    Args:
        snowflake_id: The ID to validate
        name: Human-readable name for error messages
        
    Returns:
        A tuple of (is_valid, error_message)
    """
    if not isinstance(snowflake_id, int):
        return False, f"{name} must be an integer, got {type(snowflake_id).__name__}"
    
    # Discord Snowflakes are 64-bit integers
    # They started using snowflakes around 2015, so we can do a sanity check
    # Minimum valid snowflake (roughly 2015): MIN_VALID_SNOWFLAKE
    # Maximum valid snowflake (64-bit max): MAX_VALID_SNOWFLAKE
    if snowflake_id < MIN_VALID_SNOWFLAKE:
        return False, f"{name} appears to be invalid (too small for a Discord Snowflake ID)"
    
    if snowflake_id > MAX_VALID_SNOWFLAKE:
        return False, f"{name} appears to be invalid (exceeds maximum Snowflake ID)"
    
    return True, ""


def validate_required_env_vars() -> tuple[bool, list[str]]:
    """
    Validate all required environment variables are set.
    
    Returns:
        A tuple of (all_valid, error_messages)
        - all_valid: True if all required vars are set, False otherwise
        - error_messages: List of error messages for missing/invalid variables
    """
    errors = []
    
    # Check for DISCORD_TOKEN
    token = os.getenv("DISCORD_TOKEN")
    is_valid, error_msg = validate_discord_token(token)
    if not is_valid:
        errors.append(f"❌ {error_msg}")
    
    return len(errors) == 0, errors


def print_validation_errors(errors: list[str]) -> None:
    """
    Print validation errors in a user-friendly format.
    
    Args:
        errors: List of error messages to print
    """
    print("\n" + "="*60)
    print("❌ CONFIGURATION VALIDATION FAILED")
    print("="*60)
    for error in errors:
        print(error)
    print("\n💡 Please check your .env file and ensure all required")
    print("   environment variables are set correctly.")
    print("   See .env.example for a template.\n")
    print("="*60 + "\n")


def validate_config_ids(config_module) -> tuple[bool, list[str]]:
    """
    Validate Discord IDs in the config module.
    
    Args:
        config_module: The config module containing Discord IDs
        
    Returns:
        A tuple of (all_valid, warning_messages)
    """
    warnings = []
    
    # Check ROLE_MEMBER
    if hasattr(config_module, 'ROLE_MEMBER'):
        is_valid, error_msg = validate_snowflake_id(
            config_module.ROLE_MEMBER, 
            "ROLE_MEMBER"
        )
        if not is_valid:
            warnings.append(f"⚠️  {error_msg}")
    
    # Check CHANNEL_RULES
    if hasattr(config_module, 'CHANNEL_RULES'):
        is_valid, error_msg = validate_snowflake_id(
            config_module.CHANNEL_RULES,
            "CHANNEL_RULES"
        )
        if not is_valid:
            warnings.append(f"⚠️  {error_msg}")
    
    return len(warnings) == 0, warnings


def startup_validation_check(config_module=None) -> bool:
    """
    Perform all validation checks at bot startup.
    
    Args:
        config_module: Optional config module to validate IDs
        
    Returns:
        True if all validations pass, False otherwise (bot should not start)
    """
    print("🔍 Validating configuration...")
    
    # Check required environment variables
    all_valid, errors = validate_required_env_vars()
    
    if not all_valid:
        print_validation_errors(errors)
        return False
    
    print("✅ Environment variables validated successfully")
    
    # Check config IDs if module provided
    if config_module:
        ids_valid, warnings = validate_config_ids(config_module)
        if warnings:
            print("\n⚠️  Configuration ID Warnings:")
            for warning in warnings:
                print(warning)
            print()
    
    return True
