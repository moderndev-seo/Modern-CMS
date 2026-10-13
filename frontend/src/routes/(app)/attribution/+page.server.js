import { randomUUID } from 'node:crypto';
import { redirect } from '@sveltejs/kit';
import { readPractice, writePractice } from '$lib/server/modern-practice.js';
export async function load(event) {
  return { info: await readPractice(event, 'attribution/'), requestKey: randomUUID() };
}
export const actions = {
  create: async (event) => {
    const result = await writePractice(event, 'attribution/', ['name', 'request_id']);
    if ('success' in result) redirect(303, `/attribution/${result.result.id}`);
    return result;
  }
};
