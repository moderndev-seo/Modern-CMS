import { redirect, fail, isHttpError } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
export const actions = {
  search: async (event) => {
    const fields = await event.request.formData();
    const query = String(fields.get('search') || '').trim();
    try {
      const lookup = await readPractice(
        event,
        `contacts/?${new URLSearchParams({ search: query })}`
      );
      return { lookup: { ...lookup, query } };
    } catch (problem) {
      if (!isHttpError(problem)) throw problem;
      return fail(problem.status, { lookup: { query, results: [], error: problem.body.message } });
    }
  },
  create: async (event) => {
    const result = await writePractice(event, '', [
      'contact',
      'first_name',
      'last_name',
      'email',
      'lead_at',
      'original_source',
      'original_campaign',
      'original_keyword',
      'original_landing_page',
      'original_at'
    ]);
    if ('success' in result) redirect(303, `/patients/${result.result.id}`);
    return result;
  }
};
