export const sources = [
  ['google_ads', 'Google Ads'],
  ['organic_search', 'Organic search'],
  ['meta_ads', 'Meta Ads'],
  ['referral', 'Referral'],
  ['email', 'Email'],
  ['direct', 'Direct'],
  ['unknown', 'Unknown']
];
export const eventKinds = [
  ['touch', 'Marketing touch'],
  ['booked', 'Appointment booked'],
  ['attended', 'Appointment attended'],
  ['consultation', 'Consultation'],
  ['treated', 'Treatment completed']
];
/** @param {string} source */
export const sourceLabel = (source) => sources.find(([key]) => key === source)?.[1] || 'Unknown';
/** @param {any} value */
export const usd = (value) =>
  value === null || value === undefined
    ? 'Not entered'
    : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(value));
/** @param {string} value */
export const dateTime = (value) =>
  value
    ? new Intl.DateTimeFormat('en-US', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'UTC'
      }).format(new Date(value)) + ' UTC'
    : 'Not recorded';
export const nowInput = () => new Date().toISOString().slice(0, 16);

/** Remaining balances use integer cents to avoid fractional-cent subtraction.
 * @param {{id: string, kind: string, amount: string, payment?: string | null, reference: string}[]} receipts
 */
export function refundablePayments(receipts) {
  return receipts
    .filter((entry) => entry.kind === 'payment')
    .map((payment) => {
      const refunded = receipts
        .filter((entry) => entry.kind === 'refund' && entry.payment === payment.id)
        .reduce((sum, entry) => sum + Math.round(Number(entry.amount) * 100), 0);
      return {
        ...payment,
        remaining: Math.max(0, Math.round(Number(payment.amount) * 100) - refunded) / 100
      };
    });
}
