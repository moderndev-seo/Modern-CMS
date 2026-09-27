import { isHttpError } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
/** @type {import('./$types').PageServerLoad} */
export async function load(event) {
  const query = new URLSearchParams();
  for (const key of ['start', 'end']) {
    const value = event.url.searchParams.get(key);
    if (value) query.set(key, value);
  }
  try {
    return {
      report: await readPractice(event, `growth/?${query}`),
      rangeError: null,
      start: '',
      end: ''
    };
  } catch (problem) {
    if (!isHttpError(problem, 400)) throw problem;
    return {
      report: null,
      rangeError: problem.body.message,
      start: query.get('start') || '',
      end: query.get('end') || ''
    };
  }
}
export const actions = {
  spend: (event) => writePractice(event, 'spend/', ['source', 'date', 'amount'], 'PUT')
};
