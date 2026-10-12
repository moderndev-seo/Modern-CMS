import { randomUUID } from 'node:crypto';
import { redirect } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
import { saveLocalMessage } from '$lib/server/local-messages.js';
export async function load(event) {
  return {
    detail: await readPractice(event, `messages/${event.params.id}/?${event.url.searchParams}`),
    draftKey: randomUUID(),
    stateKey: randomUUID(),
    entryKey: randomUUID()
  };
}
async function change(event, action) {
  const fields = await event.request.formData();
  const body = {
    action,
    revision: Number(fields.get('revision')),
    request_id: String(fields.get('request_id')),
    ...(action === 'draft'
      ? { draft: String(fields.get('draft') ?? '') }
      : { owner: fields.get('owner') || null, status: fields.get('status') })
  };
  const result = await saveLocalMessage(event, `${event.params.id}/`, body);
  if ('success' in result) redirect(303, `/messages/${event.params.id}?saved=1`);
  return result;
}
export const actions = {
  draft: (event) => change(event, 'draft'),
  state: (event) => change(event, 'state'),
  entry: async (event) => {
    const result = await writePractice(event, `messages/${event.params.id}/entries/`, [
      'kind',
      'body',
      'occurred_at',
      'request_id'
    ]);
    if ('success' in result) redirect(303, `/messages/${event.params.id}?saved=1`);
    return result;
  },
  followup: async (event) => {
    const { conversation } = await readPractice(event, `messages/${event.params.id}/`);
    const result = await writePractice(event, `${conversation.patient}/tasks/`, [
      'title',
      'due_date',
      'priority',
      'description'
    ]);
    if ('success' in result) redirect(303, `/messages/${event.params.id}?saved=followup`);
    return result;
  }
};
