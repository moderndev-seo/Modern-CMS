import { redirect } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
/** @type {import('./$types').PageServerLoad} */
export async function load(event) {
  const query = new URLSearchParams({ page: event.url.searchParams.get('page') || '1' });
  return { billing: await readPractice(event, `${event.params.id}/billing/?${query}`) };
}

export const actions = {
  reverse: async (event) => {
    const result = await writePractice(event, `${event.params.id}/billing/reversals/`, [
      'match',
      'reason'
    ]);
    if ('success' in result) redirect(303, `/patients/${event.params.id}/billing?reversed=1`);
    return result;
  },
  match: async (event) => {
    const result = await writePractice(event, `${event.params.id}/billing/matches/`, [
      'receipt',
      'invoice_payment',
      'reason'
    ]);
    if ('success' in result) redirect(303, `/patients/${event.params.id}/billing?matched=1`);
    return result;
  }
};
