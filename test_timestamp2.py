from datetime import datetime, timezone

print("=== Simulating the Message update cycle ===\n")

# Step 1: Agent creates Message with timestamp (via _generate_timestamp)
original_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f %Z")
print(f"1. Original timestamp (from _generate_timestamp): {original_ts}")

# Step 2: Message.model_dump() serializes it via serialize_timestamp
# serialize_timestamp in message.py tries to parse it and returns datetime
# But first, let's see what timestamp_with_fractional_seconds_validator returns
def timestamp_with_fractional_seconds(timestamp):
    if isinstance(timestamp, str):
        formats = [
            "%Y-%m-%d %H:%M:%S.%f %Z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S %Z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(timestamp.strip(), fmt).replace(tzinfo=timezone.utc)
                return parsed.strftime("%Y-%m-%d %H:%M:%S.%f %Z")
            except ValueError:
                continue
        raise ValueError(f"Invalid timestamp format: {timestamp}")
    
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f %Z")

# After validation, the Message.timestamp is a string
validated_ts = timestamp_with_fractional_seconds(original_ts)
print(f"2. After validation (timestamp_with_fractional_seconds): {validated_ts}")

# Step 3: When model_dump() is called, serialize_timestamp runs
def serialize_timestamp(value):
    formats = [
        "%Y-%m-%d %H:%M:%S.%f %Z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return value

serialized = serialize_timestamp(validated_ts)
print(f"3. After serialize_timestamp (model_dump): {serialized}, type={type(serialized)}")

# Step 4: Pydantic JSON encoder converts datetime to ISO format
# This is what actually gets sent in the response and stored
iso_format = serialized.isoformat() if isinstance(serialized, datetime) else serialized
print(f"4. After JSON encoding (ISO format): {iso_format}")

# Step 5: When Message.create(**model_dump()) is called, the timestamp goes through
# timestamp_with_fractional_seconds_validator again with ISO format
print(f"\n5. Now the ISO format goes through validator again:")
try:
    result = timestamp_with_fractional_seconds(iso_format)
    print(f"   Result: {result}")
except ValueError as e:
    print(f"   ERROR: {e}")
    print("   This is where the bug might be!")

# Let's check what formats CAN parse ISO format
print(f"\n=== Checking which formats can parse ISO ===")
formats = [
    "%Y-%m-%d %H:%M:%S.%f %Z",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f%z",
]
for fmt in formats:
    try:
        result = datetime.strptime(iso_format, fmt)
        print(f"  {fmt}: SUCCESS -> {result}")
        break
    except ValueError:
        print(f"  {fmt}: FAIL")
