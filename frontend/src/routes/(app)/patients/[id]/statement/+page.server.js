import { readPractice } from '$lib/server/modern-practice.js';
export async function load(event) {
  event.setHeaders({ 'cache-control': 'private, no-store' });
  return { statement: await readPractice(event, `${event.params.id}/statement/`) };
}
