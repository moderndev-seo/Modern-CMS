import { randomUUID } from 'node:crypto';
import { fail, redirect } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';
import { readPractice } from '$lib/server/modern-practice.js';

export async function load(event) {
  return {
    exclusions: await readPractice(event, `${event.params.id}/exclusions/`),
    patientId: event.params.id,
    requestId: randomUUID(),
    saved: event.url.searchParams.get('saved') === '1'
  };
}

export const actions = {
  default: async (event) => {
    const form = await event.request.formData();
    const values = {
      receipt: String(form.get('receipt') || ''),
      retained: String(form.get('retained') || '') || null,
      excluded: form.get('excluded') === 'true',
      revision: String(form.get('revision') || ''),
      request_id: String(form.get('request_id') || ''),
      reason: String(form.get('reason') || '')
    };
    try {
      await apiRequest(
        `/patients/${event.params.id}/exclusions/`,
        { method: 'POST', body: values },
        event.cookies
      );
    } catch (caught) {
      const problem = /** @type {any} */ (caught);
      return fail(problem.status >= 400 && problem.status < 500 ? problem.status : 502, {
        error: problem.message || 'Could not record exclusion decision.',
        values
      });
    }
    redirect(303, `/patients/${event.params.id}/exclusions?saved=1`);
  }
};
