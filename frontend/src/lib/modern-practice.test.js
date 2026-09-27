import { describe, expect, it } from 'vitest';
import { refundablePayments } from './modern-practice.js';

describe('refundable balances', () => {
  it('subtracts only refunds linked to the correct payment, in cents', () => {
    const records = [
      { id: 'a', kind: 'payment', amount: '0.30', reference: 'A' },
      { id: 'b', kind: 'payment', amount: '100.00', reference: 'B' },
      { id: 'c', kind: 'refund', amount: '0.10', payment: 'a', reference: 'C' },
      { id: 'd', kind: 'refund', amount: '0.10', payment: 'a', reference: 'D' },
      { id: 'e', kind: 'refund', amount: '25.00', payment: 'b', reference: 'E' }
    ];
    expect(refundablePayments(records).map((entry) => entry.remaining)).toEqual([0.1, 75]);
    expect(records[0].amount).toBe('0.30');
  });
  it('marks fully refunded payments unavailable and handles no receipts', () => {
    expect(refundablePayments([])).toEqual([]);
    expect(
      refundablePayments([
        { id: 'a', kind: 'payment', amount: '12.00', reference: 'A' },
        { id: 'b', kind: 'refund', amount: '12.00', payment: 'a', reference: 'B' }
      ])[0].remaining
    ).toBe(0);
  });
});
