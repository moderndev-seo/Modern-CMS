import { randomUUID } from 'node:crypto';
import { redirect } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
export async function load(event) {
  return {
    inbox: await readPractice(event, `messages/?${event.url.searchParams}`),
    requestKey: randomUUID(),
    filters: Object.fromEntries(event.url.searchParams)
  };
}
export const actions = {
  create: async (event) => {
    const result = await writePractice(event, 'messages/', ['patient', 'subject', 'request_id']);
    if ('success' in result) redirect(303, `/messages/${result.result.id}`);
    return result;
  }
};
