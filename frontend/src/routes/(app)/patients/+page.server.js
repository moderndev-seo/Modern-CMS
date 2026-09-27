import { readPractice } from '$lib/server/modern-practice.js';
/** @type {import('./$types').PageServerLoad} */
export async function load(event) {
  const query = new URLSearchParams({
    search: event.url.searchParams.get('search') || '',
    page: event.url.searchParams.get('page') || '1'
  });
  return { patients: await readPractice(event, `?${query}`), search: query.get('search') };
}
