import { error, fail } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';

/** @param {any} event @param {string} path */
export async function readPractice(event, path) {
  try {
    return await apiRequest(`/patients/${path}`, {}, event.cookies);
  } catch (caught) {
    const problem = /** @type {any} */ (caught);
    error(problem.status || 502, problem.message || 'Could not load practice records.');
  }
}

/** @param {any} event @param {string} path @param {string[]} fields @param {string} method */
export async function writePractice(event, path, fields, method = 'POST') {
  const form = await event.request.formData();
  /** @type {Record<string, any>} */
  const body = {};
  for (const key of fields) {
    const value = String(form.get(key) ?? '').trim();
    if (value) body[key] = key.endsWith('_at') ? `${value}Z` : value;
  }
  try {
    const result = await apiRequest(`/patients/${path}`, { method, body }, event.cookies);
    return { success: true, result };
  } catch (caught) {
    const problem = /** @type {any} */ (caught);
    return fail(problem.status >= 400 && problem.status < 500 ? problem.status : 502, {
      error: problem.message || 'Could not save. Try again.',
      action: path.split('/').filter(Boolean).at(-1),
      values: Object.fromEntries(form)
    });
  }
}
