import { randomUUID } from 'node:crypto';
import { fail, redirect } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
export async function load(event) {
  return {
    detail: await readPractice(event, `reviews/${event.params.id}/?${event.url.searchParams}`),
    draftKey: randomUUID(),
    statusKey: randomUUID()
  };
}
async function change(event, action) {
  const fields = await event.request.formData();
  const values = {
    action,
    revision: Number(fields.get('revision')),
    request_id: String(fields.get('request_id')),
    ...(action === 'draft'
      ? { draft: String(fields.get('draft') ?? '') }
      : { status: String(fields.get('status')), reason: String(fields.get('reason') ?? '') })
  };
  try {
    await apiRequest(
      `/patients/reviews/${event.params.id}/`,
      { method: 'PATCH', body: values },
      event.cookies
    );
  } catch (caught) {
    const problem = /** @type {any} */ (caught);
    return fail(problem.status >= 400 && problem.status < 500 ? problem.status : 502, {
      error: problem.message || 'Could not save. Reload and review.',
      values
    });
  }
  redirect(303, `/reviews/${event.params.id}?saved=1`);
}
export const actions = {
  draft: (event) => change(event, 'draft'),
  status: (event) => change(event, 'status'),
  followup: async (event) => {
    const { review } = await readPractice(event, `reviews/${event.params.id}/`);
    const result = await writePractice(event, `${review.patient}/tasks/`, [
      'title',
      'due_date',
      'description'
    ]);
    if ('success' in result) redirect(303, `/reviews/${event.params.id}?saved=followup`);
    return result;
  }
};
