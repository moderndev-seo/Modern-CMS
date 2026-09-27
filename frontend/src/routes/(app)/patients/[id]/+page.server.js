import { fail } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
/** @type {import('./$types').PageServerLoad} */
export async function load(event) {
  return { patient: await readPractice(event, `${event.params.id}/`) };
}
export const actions = {
  followup: (event) =>
    writePractice(event, `${event.params.id}/tasks/`, [
      'title',
      'due_date',
      'priority',
      'description'
    ]),
  taskStatus: async (event) => {
    const fields = await event.request.clone().formData();
    const id = String(fields.get('task_id') || '');
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id))
      return fail(400, { error: 'Choose a valid task.' });
    return writePractice(event, `${event.params.id}/tasks/${id}/`, ['status'], 'PATCH');
  },
  event: (event) =>
    writePractice(event, `${event.params.id}/events/`, [
      'kind',
      'occurred_at',
      'source',
      'campaign',
      'landing_page',
      'notes'
    ]),
  receipt: (event) =>
    writePractice(event, `${event.params.id}/receipts/`, [
      'kind',
      'amount',
      'occurred_at',
      'payment',
      'reference',
      'notes'
    ])
};
