import { fail } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';
import { readPractice } from '$lib/server/modern-practice.js';

export async function load(event) {
  return {
    info: await readPractice(
      event,
      `attribution/${event.params.id}/events/?${event.url.searchParams}`
    )
  };
}
export const actions = {
  demo: async (event) => {
    const path = `/patients/attribution/${event.params.id}/events/`;
    const records = [
      [
        'lead',
        {
          first_name: 'Fictional',
          last_name: 'Attribution Demo',
          lead_at: '2026-09-02T12:00:00Z',
          original_source: 'google_ads',
          original_campaign: 'TEST attribution campaign',
          original_landing_page: 'https://example.com/test',
          original_at: '2026-09-01T12:00:00Z'
        }
      ],
      [
        'touch',
        { source: 'email', campaign: 'TEST later touch', occurred_at: '2026-09-03T12:00:00Z' }
      ],
      ['booked', { occurred_at: '2026-09-04T12:00:00Z' }],
      ['attended', { occurred_at: '2026-09-05T12:00:00Z' }],
      ['consultation', { occurred_at: '2026-09-05T12:30:00Z' }],
      ['treated', { occurred_at: '2026-09-06T12:00:00Z' }],
      ['payment', { amount: '1200.00', currency: 'USD', occurred_at: '2026-09-07T12:00:00Z' }],
      [
        'refund',
        {
          amount: '100.00',
          currency: 'USD',
          payment_event_id: 'demo-payment',
          occurred_at: '2026-09-08T12:00:00Z'
        }
      ]
    ];
    let imported = 0;
    let replayed = 0;
    try {
      for (const [kind, data] of records) {
        const result = await apiRequest(
          path,
          {
            method: 'POST',
            body: { event_id: `demo-${kind}`, subject_id: 'demo-patient', kind, data }
          },
          event.cookies
        );
        if (result.replayed) replayed += 1;
        else imported += 1;
      }
      return {
        success: `${imported} new events; ${replayed} existing events safely replayed. Demo cash: $1,200 received less $100 refunded = $1,100 net, unless subsequently corrected.`
      };
    } catch (caught) {
      const problem = /** @type {any} */ (caught);
      return fail(problem.status >= 400 && problem.status < 500 ? problem.status : 502, {
        error: `${imported} new events saved before stopping. Retry resumes without duplicates. ${problem.message || 'Could not import the next event.'}`
      });
    }
  }
};
