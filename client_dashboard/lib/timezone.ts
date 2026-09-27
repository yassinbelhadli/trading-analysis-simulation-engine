/**
 * Timezone/date formatting utility — shared across all dashboards.
 * All timestamps from the backend are UTC. This converts to user's timezone.
 */

// Mirror of the backend TIMEZONE_REGIONS
export const TIMEZONE_REGIONS = [
  {
    region: "Africa",
    timezones: [
      { label: "Morocco — Casablanca", iana: "Africa/Casablanca" },
      { label: "Algeria — Algiers", iana: "Africa/Algiers" },
      { label: "Tunisia — Tunis", iana: "Africa/Tunis" },
      { label: "Egypt — Cairo", iana: "Africa/Cairo" },
      { label: "South Africa — Johannesburg", iana: "Africa/Johannesburg" },
      { label: "Nigeria — Lagos", iana: "Africa/Lagos" },
      { label: "Kenya — Nairobi", iana: "Africa/Nairobi" },
    ],
  },
  {
    region: "Europe",
    timezones: [
      { label: "France — Paris", iana: "Europe/Paris" },
      { label: "UK — London", iana: "Europe/London" },
      { label: "Germany — Berlin", iana: "Europe/Berlin" },
      { label: "Spain — Madrid", iana: "Europe/Madrid" },
      { label: "Italy — Rome", iana: "Europe/Rome" },
      { label: "Netherlands — Amsterdam", iana: "Europe/Amsterdam" },
      { label: "Portugal — Lisbon", iana: "Europe/Lisbon" },
    ],
  },
  {
    region: "North America",
    timezones: [
      { label: "United States — New York", iana: "America/New_York" },
      { label: "United States — Los Angeles", iana: "America/Los_Angeles" },
      { label: "United States — Chicago", iana: "America/Chicago" },
      { label: "United States — Denver", iana: "America/Denver" },
      { label: "Canada — Toronto", iana: "America/Toronto" },
      { label: "Canada — Vancouver", iana: "America/Vancouver" },
      { label: "Mexico — Mexico City", iana: "America/Mexico_City" },
    ],
  },
  {
    region: "South America",
    timezones: [
      { label: "Brazil — São Paulo", iana: "America/Sao_Paulo" },
      { label: "Argentina — Buenos Aires", iana: "America/Argentina/Buenos_Aires" },
      { label: "Colombia — Bogota", iana: "America/Bogota" },
    ],
  },
  {
    region: "Asia",
    timezones: [
      { label: "UAE — Dubai", iana: "Asia/Dubai" },
      { label: "Saudi Arabia — Riyadh", iana: "Asia/Riyadh" },
      { label: "Turkey — Istanbul", iana: "Europe/Istanbul" },
      { label: "India — Mumbai", iana: "Asia/Kolkata" },
      { label: "Pakistan — Karachi", iana: "Asia/Karachi" },
      { label: "Japan — Tokyo", iana: "Asia/Tokyo" },
      { label: "China — Shanghai", iana: "Asia/Shanghai" },
      { label: "South Korea — Seoul", iana: "Asia/Seoul" },
      { label: "Singapore", iana: "Asia/Singapore" },
      { label: "Hong Kong", iana: "Asia/Hong_Kong" },
      { label: "Thailand — Bangkok", iana: "Asia/Bangkok" },
      { label: "Indonesia — Jakarta", iana: "Asia/Jakarta" },
    ],
  },
  {
    region: "Oceania",
    timezones: [
      { label: "Australia — Sydney", iana: "Australia/Sydney" },
      { label: "Australia — Melbourne", iana: "Australia/Melbourne" },
      { label: "New Zealand — Auckland", iana: "Pacific/Auckland" },
    ],
  },
];

export const DEFAULT_TIMEZONE = "Africa/Casablanca";

/**
 * Format a UTC timestamp (Date, ISO string, or epoch ms) in the user's timezone.
 */
export function formatUserDateTime(timestamp: Date | string | number, timezone: string): string {
  const date = typeof timestamp === "string" || typeof timestamp === "number"
    ? new Date(timestamp)
    : timestamp;
  try {
    return date.toLocaleString("en-GB", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return date.toLocaleString("en-GB");
  }
}

/**
 * Format date only.
 */
export function formatUserDate(timestamp: Date | string | number, timezone: string): string {
  const date = typeof timestamp === "string" || typeof timestamp === "number"
    ? new Date(timestamp)
    : timestamp;
  try {
    return date.toLocaleDateString("en-GB", {
      timeZone: timezone,
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return date.toLocaleDateString("en-GB");
  }
}

/**
 * Format time only.
 */
export function formatUserTime(timestamp: Date | string | number, timezone: string): string {
  const date = typeof timestamp === "string" || typeof timestamp === "number"
    ? new Date(timestamp)
    : timestamp;
  try {
    return date.toLocaleTimeString("en-GB", {
      timeZone: timezone,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return date.toLocaleTimeString("en-GB");
  }
}

/**
 * Get a human-readable timezone label from IANA ID.
 */
export function getTimezoneLabel(iana: string): string {
  for (const region of TIMEZONE_REGIONS) {
    for (const tz of region.timezones) {
      if (tz.iana === iana) return tz.label;
    }
  }
  return iana;
}

/**
 * Get the current time in a given timezone as a live-updating string.
 */
export function getCurrentTimeInTimezone(timezone: string): { time: string; date: string } {
  const now = new Date();
  return {
    time: formatUserTime(now, timezone),
    date: formatUserDate(now, timezone),
  };
}
