from datetime import datetime, timezone

from loguru import logger
from pydantic import BeforeValidator


def timestamp_to_str(timestamp: datetime | str) -> str:
    """Convert timestamp to standardized string format.

    Handles multiple input formats and ensures consistent UTC timezone output.

    Args:
        timestamp (datetime | str): Input timestamp either as datetime object or string

    Returns:
        str: Formatted timestamp string in 'YYYY-MM-DD HH:MM:SS UTC' format

    Raises:
        ValueError: If string timestamp is in invalid format
    """
    logger.info(f"[TIMESTAMP_TO_STR] Input: {timestamp!r}, type: {type(timestamp)}")
    if isinstance(timestamp, str):
        # Try parsing with different formats
        formats = [
            "%Y-%m-%d %H:%M:%S.%f%z",   # With fractional seconds and numeric timezone
            "%Y-%m-%d %H:%M:%S.%f %Z",  # With fractional seconds and timezone name
            "%Y-%m-%d %H:%M:%S.%f",     # With fractional seconds, no timezone
            "%Y-%m-%dT%H:%M:%S.%f%z",   # ISO with microseconds and numeric timezone
            "%Y-%m-%dT%H:%M:%S.%f",     # ISO with microseconds
            "%Y-%m-%d %H:%M:%S%z",      # With numeric timezone
            "%Y-%m-%d %H:%M:%S %Z",     # Standard with timezone name
            "%Y-%m-%d %H:%M:%S",        # Without timezone
            "%Y-%m-%dT%H:%M:%S%z",      # ISO with numeric timezone
            "%Y-%m-%dT%H:%M:%S",        # ISO format
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt)
                # If no timezone info, assume UTC
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                result = parsed.strftime("%Y-%m-%d %H:%M:%S %Z")
                logger.info(f"[TIMESTAMP_TO_STR] Parsed with fmt={fmt}, parsed={parsed!r}, result: {result}")
                return result
            except ValueError:
                continue

        msg = f"Invalid timestamp format: {timestamp}"
        raise ValueError(msg)

    # Handle datetime object
    logger.info(f"[TIMESTAMP_TO_STR] Handling datetime: {timestamp!r}, tzinfo={timestamp.tzinfo}")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
        logger.info(f"[TIMESTAMP_TO_STR] Added UTC timezone: {timestamp!r}")
    result = timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")
    logger.info(f"[TIMESTAMP_TO_STR] From datetime, result: {result}")
    return result


def str_to_timestamp(timestamp: str | datetime) -> datetime:
    """Convert timestamp to datetime object.

    Handles multiple input formats and ensures consistent UTC timezone output.

    Args:
        timestamp (str | datetime): Input timestamp either as string or datetime object

    Returns:
        datetime: Datetime object with UTC timezone

    Raises:
        ValueError: If string timestamp is not in a valid format
    """
    logger.info(f"[STR_TO_TIMESTAMP] Input: {timestamp!r}, type: {type(timestamp)}")
    if isinstance(timestamp, str):
        # Try parsing with multiple formats
        formats = [
            "%Y-%m-%d %H:%M:%S.%f%z",   # With fractional seconds and numeric timezone
            "%Y-%m-%d %H:%M:%S.%f %Z",  # With fractional seconds and timezone name
            "%Y-%m-%d %H:%M:%S.%f",     # With fractional seconds, no timezone
            "%Y-%m-%d %H:%M:%S%z",      # With numeric timezone
            "%Y-%m-%d %H:%M:%S %Z",     # Standard with timezone name
            "%Y-%m-%d %H:%M:%S",        # Without timezone
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt)
                # If no timezone info, assume UTC
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                logger.info(f"[STR_TO_TIMESTAMP] Parsed with fmt={fmt}, result: {parsed!r}")
                return parsed
            except ValueError:
                continue
        msg = f"Invalid timestamp format: {timestamp}. Expected format: YYYY-MM-DD HH:MM:SS UTC"
        raise ValueError(msg)
    # If already a datetime, ensure it has UTC timezone
    logger.info(f"[STR_TO_TIMESTAMP] Input is datetime: {timestamp!r}, tzinfo={timestamp.tzinfo}")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
        logger.info(f"[STR_TO_TIMESTAMP] Added UTC timezone: {timestamp!r}")
    logger.info(f"[STR_TO_TIMESTAMP] Returning: {timestamp!r}")
    return timestamp


def timestamp_with_fractional_seconds(timestamp: datetime | str) -> str:
    """Convert timestamp to string format including fractional seconds.

    Handles multiple input formats and ensures consistent UTC timezone output.

    Args:
        timestamp (datetime | str): Input timestamp either as datetime object or string

    Returns:
        str: Formatted timestamp string in 'YYYY-MM-DD HH:MM:SS.ffffff UTC' format

    Raises:
        ValueError: If string timestamp is in invalid format
    """
    if isinstance(timestamp, str):
        # Try parsing with different formats
        formats = [
            "%Y-%m-%d %H:%M:%S.%f%z",   # With fractional seconds and numeric timezone
            "%Y-%m-%d %H:%M:%S.%f %Z",  # Standard with timezone name
            "%Y-%m-%d %H:%M:%S.%f",     # Without timezone
            "%Y-%m-%dT%H:%M:%S.%f%z",   # ISO with numeric timezone
            "%Y-%m-%dT%H:%M:%S.%f",     # ISO format
            # Also try without fractional seconds
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S %Z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt)
                # If no timezone info, assume UTC
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.strftime("%Y-%m-%d %H:%M:%S.%f %Z")
            except ValueError:
                continue

        msg = f"Invalid timestamp format: {timestamp}"
        raise ValueError(msg)

    # Handle datetime object
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f %Z")


timestamp_to_str_validator = BeforeValidator(timestamp_to_str)
timestamp_with_fractional_seconds_validator = BeforeValidator(timestamp_with_fractional_seconds)
str_to_timestamp_validator = BeforeValidator(str_to_timestamp)


def str_to_naive_timestamp(timestamp: str | datetime) -> datetime:
    """Convert timestamp to naive datetime object for database storage.
    
    This validator is specifically for database models using 'timestamp without time zone'.
    It ensures timestamps are stored as naive datetimes to prevent PostgreSQL from
    applying timezone conversions.
    
    Args:
        timestamp (str | datetime): Input timestamp either as string or datetime object
        
    Returns:
        datetime: Naive datetime object (no timezone info)
    """
    logger.info(f"[STR_TO_NAIVE_TIMESTAMP] Input: {timestamp!r}, type: {type(timestamp)}")
    
    if isinstance(timestamp, str):
        # Try parsing with multiple formats
        formats = [
            "%Y-%m-%d %H:%M:%S.%f%z",   # With fractional seconds and numeric timezone
            "%Y-%m-%d %H:%M:%S.%f %Z",  # With fractional seconds and timezone name
            "%Y-%m-%d %H:%M:%S.%f",     # With fractional seconds, no timezone
            "%Y-%m-%d %H:%M:%S%z",      # With numeric timezone
            "%Y-%m-%d %H:%M:%S %Z",     # Standard with timezone name
            "%Y-%m-%d %H:%M:%S",        # Without timezone
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt)
                # Always return naive datetime for DB storage
                if parsed.tzinfo is not None:
                    parsed = parsed.replace(tzinfo=None)
                logger.info(f"[STR_TO_NAIVE_TIMESTAMP] Parsed with fmt={fmt}, result: {parsed!r}")
                return parsed
            except ValueError:
                continue
        msg = f"Invalid timestamp format: {timestamp}. Expected format: YYYY-MM-DD HH:MM:SS"
        raise ValueError(msg)
    
    # If already a datetime, strip timezone for DB storage
    logger.info(f"[STR_TO_NAIVE_TIMESTAMP] Input is datetime: {timestamp!r}, tzinfo={timestamp.tzinfo}")
    if timestamp.tzinfo is not None:
        # Already has timezone - just strip it to keep the same time values
        result = timestamp.replace(tzinfo=None)
        logger.info(f"[STR_TO_NAIVE_TIMESTAMP] Stripped timezone: {result!r}")
        return result
    logger.info(f"[STR_TO_NAIVE_TIMESTAMP] Already naive, returning: {timestamp!r}")
    return timestamp


str_to_naive_timestamp_validator = BeforeValidator(str_to_naive_timestamp)
