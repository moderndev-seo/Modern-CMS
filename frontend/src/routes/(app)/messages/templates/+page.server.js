import { randomUUID } from 'node:crypto';
import { fail, redirect } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
import { saveLocalMessage } from '$lib/server/local-messages.js';
export async function load(event) {
  return {
    info: await readPractice(event, `messages/templates/?${event.url.searchParams}`),
    requestKey: randomUUID()
  };
}
export const actions = {
  create: async (event) => {
    const result = await writePractice(event, 'messages/templates/', [
      'title',
      'body',
      'request_id'
    ]);
    if ('success' in result) redirect(303, '/messages/templates?saved=1');
    return result;
  },
  state: async (event) => {
    const fields = await event.request.formData();
    const id = String(fields.get('id'));
    if (!/^[0-9a-f-]{36}$/i.test(id)) return fail(400, { error: 'Choose a valid template.' });
    const result = await saveLocalMessage(event, `templates/${id}/`, {
      active: fields.get('active') === 'true',
      revision: Number(fields.get('revision'))
    });
    if ('success' in result) redirect(303, '/messages/templates?saved=1');
    return result;
  }
};
