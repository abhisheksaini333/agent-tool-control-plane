/** A stalled identity/API connection must leave the operator a recoverable state. */
export async function fetchBounded(
  url: string,
  options: RequestInit = {},
  timeoutMs = 10000
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted)
      throw new Error("The service timed out. Retry when it is available.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
