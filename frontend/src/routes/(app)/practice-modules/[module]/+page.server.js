import { error } from '@sveltejs/kit';
/** @type {import('./$types').PageServerLoad} */
export function load({ params }) {
  const labels = { messages: 'Messages', reviews: 'Reviews' };
  if (!(params.module in labels)) error(404, 'Module not found');
  return { moduleName: labels[params.module] };
}
