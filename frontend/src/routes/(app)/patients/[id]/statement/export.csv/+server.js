import { readPractice } from '$lib/server/modern-practice.js';
export async function GET(event) {
  const data = await readPractice(event, `${event.params.id}/statement/?download=csv`);
  return new Response(data.csv, {
    headers: {
      'content-type': 'text/csv; charset=utf-8',
      'content-disposition': 'attachment; filename="modern-practice-internal-statement.csv"',
      'cache-control': 'private, no-store',
      'x-content-type-options': 'nosniff'
    }
  });
}
