import { fail } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';
/** Preserve explicit blank drafts and null owners; the API validates all writes. */
export async function saveLocalMessage(event, path, body, method = 'PATCH') {
  try {
    const result = await apiRequest(`/patients/messages/${path}`, { method, body }, event.cookies);
    return { success: true, result };
  } catch (caught) {
    const problem = /** @type {any} */ (caught);
    return fail(problem.status >= 400 && problem.status < 500 ? problem.status : 502, {
      error: problem.message || 'Could not save. Reload and review.',
      values: body
    });
  }
}
