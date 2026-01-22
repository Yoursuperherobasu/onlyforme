import type { ChatMessageType } from "../../../../../types/chat";

// Cache for parsed timestamps to improve performance during sorting
const timestampCache = new WeakMap<ChatMessageType, number>();

/**
 * Parse a timestamp string into a Date object.
 * Handles multiple formats including those with microseconds.
 * @param timestamp - The timestamp string to parse
 * @returns The timestamp as milliseconds since epoch
 */
const parseTimestamp = (timestamp: string): number => {
  // Try native Date parsing first (works for ISO formats)
  let time = new Date(timestamp).getTime();
  if (!isNaN(time)) {
    return time;
  }

  // Handle our custom format: "YYYY-MM-DD HH:MM:SS.ffffff UTC" or "YYYY-MM-DD HH:MM:SS UTC"
  // Convert to ISO format for reliable parsing
  const match = timestamp.match(
    /^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(?:\.(\d+))?\s*(UTC)?$/,
  );
  if (match) {
    const [, datePart, timePart, microSeconds, tz] = match;
    // Convert microseconds to milliseconds (take first 3 digits)
    const ms = microSeconds ? microSeconds.slice(0, 3).padEnd(3, "0") : "000";
    const isoString = `${datePart}T${timePart}.${ms}Z`;
    time = new Date(isoString).getTime();
    if (!isNaN(time)) {
      // Add remaining microseconds precision for comparison (as fraction of ms)
      if (microSeconds && microSeconds.length > 3) {
        const remainingMicros = parseInt(microSeconds.slice(3).padEnd(3, "0"));
        time += remainingMicros / 1000;
      }
      return time;
    }
  }

  // Fallback: return 0 for unparseable timestamps
  return 0;
};

/**
 * Sorts chat messages by timestamp with proper handling of identical timestamps.
 *
 * Primary sort: By timestamp (chronological order)
 * Secondary sort: When timestamps are identical, User messages (isSend=true) come before AI/Machine messages (isSend=false)
 *
 * This ensures proper conversation flow even when backend generates identical timestamps
 * due to streaming, load balancing, or database precision limitations.
 *
 * @param a - First chat message to compare
 * @param b - Second chat message to compare
 * @returns Sort comparison result (-1, 0, 1)
 */
const sortSenderMessages = (a: ChatMessageType, b: ChatMessageType): number => {
  // Use WeakMap cache to avoid repeated Date parsing for same message objects
  let timeA = timestampCache.get(a);
  if (timeA === undefined) {
    timeA = parseTimestamp(a.timestamp);
    timestampCache.set(a, timeA);
  }

  let timeB = timestampCache.get(b);
  if (timeB === undefined) {
    timeB = parseTimestamp(b.timestamp);
    timestampCache.set(b, timeB);
  }

  // Primary sort: by timestamp
  if (timeA !== timeB) {
    return timeA - timeB;
  }

  // Secondary sort: if timestamps are identical, User messages come before AI/Machine
  // This ensures proper chronological order when backend generates identical timestamps
  if (a.isSend && !b.isSend) {
    return -1; // User message (isSend=true) comes first
  }
  if (!a.isSend && b.isSend) {
    return 1; // User message (isSend=true) comes first
  }

  return 0; // Keep original order for same sender types
};

export default sortSenderMessages;
export { parseTimestamp };
