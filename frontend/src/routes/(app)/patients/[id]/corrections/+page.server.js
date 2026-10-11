import { randomUUID } from 'node:crypto';
import { fail, redirect } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';
import { readPractice } from '$lib/server/modern-practice.js';

export async function load(event) {
  return {
    corrections: await readPractice(event, `${event.params.id}/corrections/`),
    patientId: event.params.id,
    requestId: randomUUID(),
    saved: event.url.searchParams.get('saved') === '1'
  };
}

export const actions = {
  default: async (event) => {
    const form = await event.request.formData();
    const values = Object.fromEntries(
      [
        'receipt',
        'revision',
        'request_id',
        form.has('reference') ? 'reference' : 'amount',
        'reason'
      ].map((key) => [key, String(form.get(key) || '')])
    );
    try {
      await apiRequest(
        `/patients/${event.params.id}/corrections/`,
        { method: 'POST', body: values },
        event.cookies
      );
    } catch (caught) {
      const problem = /** @type {any} */ (caught);
      return fail(problem.status >= 400 && problem.status < 500 ? problem.status : 502, {
        error: problem.message || 'Could not record correction.',
        values
      });
    }
    redirect(303, `/patients/${event.params.id}/corrections?saved=1`);
  }
};
