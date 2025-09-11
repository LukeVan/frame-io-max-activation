"""
Utility functions for the Frame.io CLI
"""
import re

def is_valid_uuid(uuid_string):
    """
    Check if a string is a valid UUID.
    
    Args:
        uuid_string (str): The string to check
        
    Returns:
        bool: True if the string is a valid UUID, False otherwise
    """
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    return bool(uuid_pattern.match(uuid_string)) 