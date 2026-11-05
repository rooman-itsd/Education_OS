import { ApiError } from '../../api/client';

/** What an admin screen says when the API refuses or is missing, the same way on every super admin screen. */
export function describeFailure(e: unknown, what: string): { message: string; retry: boolean; expired: boolean } {
  if (e instanceof ApiError && e.status === 401) return { message: 'Your session has ended. Sign in again.', retry: false, expired: true };
  if (e instanceof ApiError && e.status === 403) return { message: `You do not have access to ${what}.`, retry: false, expired: false };
  if (!(e instanceof ApiError) || [404, 502, 503].includes(e.status)) {
    return { message: `${what[0]!.toUpperCase()}${what.slice(1)} are not available yet.`, retry: true, expired: false };
  }
  const detail = (e.body as { detail?: unknown } | undefined)?.detail;
  const why = typeof detail === 'string' ? ` ${detail}` : '';
  return { message: `Could not load ${what}.${why}`, retry: true, expired: false };
}

/** The API's own words for a refused change (a 4xx with a detail), else a plain sentence. */
export function actionFailure(e: unknown): string {
  if (e instanceof ApiError) {
    const detail = (e.body as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (e.status === 403) return 'You do not have permission to do this.';
    if ([404, 502, 503].includes(e.status)) return 'The service is not available right now. Try again in a moment.';
  }
  return e instanceof Error && e.message ? e.message : 'That did not work. Try again in a moment.';
}
