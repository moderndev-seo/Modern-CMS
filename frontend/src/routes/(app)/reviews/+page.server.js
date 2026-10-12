import { randomUUID } from 'node:crypto';
import { redirect } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
export async function load(event) {
  return {
    info: await readPractice(event, `reviews/?${event.url.searchParams}`),
    filters: Object.fromEntries(event.url.searchParams),
    requestKey: randomUUID()
  };
}
export const actions = {
  create: async (event) => {
    const result = await writePractice(event, 'reviews/', [
      'patient',
      'source',
      'rating',
      'body',
      'reviewed_at',
      'request_id'
    ]);
    if ('success' in result) redirect(303, `/reviews/${result.result.id}`);
    return result;
  }
};
