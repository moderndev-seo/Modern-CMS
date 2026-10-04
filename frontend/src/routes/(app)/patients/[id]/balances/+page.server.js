import { readPractice } from '$lib/server/modern-practice.js';
export async function load(event) {
  return {
    balances: await readPractice(event, `${event.params.id}/balances/`),
    patientId: event.params.id
  };
}
