/**
 * Parse API error messages into user-friendly text.
 * Rules: 403→Access Denied, 401→Session expired, 404→Not found, 500→Server error, network→Unable to connect
 * Also extracts `detail` from JSON error bodies for 400/409/etc.
 */
export function parseApiError(error: unknown): string {
  const msg = error instanceof Error ? error.message : String(error);
  
  // Network errors
  if (msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("Network request failed")) {
    return "Unable to connect. Please check your internet connection and try again.";
  }
  
  // API status codes with known messages
  if (msg.includes("API 403")) return "Access Denied — You do not have permission to perform this action.";
  if (msg.includes("API 401")) return "Session expired. Please sign in again.";
  if (msg.includes("API 404")) return "Not found — The requested resource does not exist.";
  if (msg.includes("API 500") || msg.includes("API 502") || msg.includes("API 503")) {
    return "Server error. Please try again later.";
  }
  
  // Try to extract `detail` from JSON error body: "API 409: {"detail":"..."}"
  const jsonMatch = msg.match(/\{[\s\S]*"detail"\s*:\s*"([^"]+)"[\s\S]*\}/);
  if (jsonMatch) {
    return jsonMatch[1];
  }
  
  // Default: show original message but strip the "API xxx: " prefix if present
  const cleaned = msg.replace(/^API \d+:\s*/, "");
  return cleaned || "An unexpected error occurred.";
}
