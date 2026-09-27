import { randomUUID } from 'node:crypto';
import { error, fail, redirect } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** @type {import('./$types').PageServerLoad} */
export async function load(event) {
  const page = event.url.searchParams.get('page') || '1';
  const [patient, appointments] = await Promise.all([
    readPractice(event, `${event.params.id}/`),
    readPractice(event, `${event.params.id}/appointments/?${new URLSearchParams({ page })}`)
  ]);
  const selected = event.url.searchParams.get('appointment') || appointments.results[0]?.id;
  if (selected && !uuid.test(selected)) error(400, 'Choose a valid appointment.');
  return {
    patient,
    appointments,
    bookingKey: randomUUID(),
    selected: selected
      ? await readPractice(event, `${event.params.id}/appointments/${selected}/`)
      : null
  };
}
export const actions = {
  book: async (event) => {
    const result = await writePractice(event, `${event.params.id}/appointments/`, [
      'request_id',
      'title',
      'location',
      'starts_at',
      'ends_at'
    ]);
    if ('success' in result)
      redirect(
        303,
        `/patients/${event.params.id}/appointments?appointment=${result.result.id}&saved=1`
      );
    return result;
  },
  change: async (event) => {
    const fields = await event.request.clone().formData();
    const id = String(fields.get('appointment_id') || '');
    if (!uuid.test(id)) return fail(400, { error: 'Choose a valid appointment.' });
    const result = await writePractice(
      event,
      `${event.params.id}/appointments/${id}/`,
      ['action', 'revision', 'reason', 'starts_at', 'ends_at'],
      'PATCH'
    );
    if ('success' in result)
      redirect(303, `/patients/${event.params.id}/appointments?appointment=${id}&saved=1`);
    return result;
  }
};
