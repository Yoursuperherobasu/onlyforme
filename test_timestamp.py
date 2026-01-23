from datetime import datetime, timezone

# Test 1: ISO format with +00:00 (what model_dump() produces)
ts_iso = '2026-01-17T00:48:03.435827+00:00'
print(f'=== Test 1: ISO format with +00:00 ===')
print(f'Input: {ts_iso}')

formats = [
    '%Y-%m-%d %H:%M:%S.%f %Z',
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M:%S %Z',
    '%Y-%m-%d %H:%M:%S',
]

matched = False
for fmt in formats:
    try:
        result = datetime.strptime(ts_iso.strip(), fmt).replace(tzinfo=timezone.utc)
        print(f'Matched: {fmt} -> {result}')
        matched = True
        break
    except ValueError as e:
        print(f'Failed: {fmt}')

if not matched:
    print('!!! NO FORMAT MATCHED - serialize_timestamp returns as-is !!!')

# Test 2: What happens with fromisoformat
print(f'\n=== Test 2: fromisoformat on ISO ===')
dt = datetime.fromisoformat(ts_iso)
print(f'Result: {dt}, tzinfo: {dt.tzinfo}')

# Test 3: The CRITICAL issue - what if we call replace on already-tz-aware datetime?
print(f'\n=== Test 3: replace(tzinfo=utc) on tz-aware datetime ===')
dt_replaced = dt.replace(tzinfo=timezone.utc)
print(f'After replace: {dt_replaced}')
print(f'Same as original? {dt == dt_replaced}')

# Test 4: What strptime with %Z does with "UTC"
print(f'\n=== Test 4: strptime with %Z and "UTC" ===')
ts_utc = '2026-01-17 00:48:03.435827 UTC'
result = datetime.strptime(ts_utc, '%Y-%m-%d %H:%M:%S.%f %Z')
print(f'Input: {ts_utc}')
print(f'Result: {result}, tzinfo: {result.tzinfo}')
print(f'After replace(utc): {result.replace(tzinfo=timezone.utc)}')
