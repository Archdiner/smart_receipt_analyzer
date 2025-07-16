import json
from datetime import datetime
from typing import Any

def json_serial(obj: Any) -> str:
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def format_json_for_logging(data: Any, indent: int = 2) -> str:
    """Format data for logging with proper JSON serialization"""
    return json.dumps(data, default=json_serial, indent=indent) 