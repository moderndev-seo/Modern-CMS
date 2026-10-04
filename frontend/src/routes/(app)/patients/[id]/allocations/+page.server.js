import { randomUUID } from 'node:crypto';
import { fail, redirect } from '@sveltejs/kit';
import { apiRequest } from '$lib/api-helpers.js';
import { readPractice } from '$lib/server/modern-practice.js';

export async function load(event) {
  return {
    allocations: await readPractice(event, `${event.params.id}/allocations/`),
    patientId: event.params.id,
    selectedReceipt: event.url.searchParams.get('receipt'),
    requestId: randomUUID(),
    saved: event.url.searchParams.get('saved') === '1'
  };
}

export const actions = {
  default: async (event) => {
    const form = await event.request.formData();
    const invoices = form.getAll('invoice');
    const amounts = form.getAll('amount');
    const refundIds = form.getAll('refund');
    const refundInvoices = form.getAll('refund_invoice');
    const refundAmounts = form.getAll('refund_amount');
    const values = {
      refund_lines:
        form.get('clear') === '1'
          ? []
          : refundIds
              .map((refund, index) => ({
                refund: String(refund),
                invoice:
                  refundInvoices[index] === 'unallocated'
                    ? null
                    : String(refundInvoices[index] || ''),
                amount: String(refundAmounts[index] || '')
              }))
              .filter((line) => line.refund || line.invoice || line.amount),
      receipt: String(form.get('receipt') || ''),
      revision: String(form.get('revision') || '0'),
      request_id: String(form.get('request_id') || ''),
      reason: String(form.get('reason') || ''),
      lines:
        form.get('clear') === '1'
          ? []
          : invoices
              .map((invoice, index) => ({
                invoice: String(invoice),
                amount: String(amounts[index] || '')
              }))
              .filter((line) => line.invoice || line.amount)
    };
    try {
      await apiRequest(
        `/patients/${event.params.id}/allocations/`,
        { method: 'POST', body: values },
        event.cookies
      );
    } catch (caught) {
      const problem = /** @type {any} */ (caught);
      return fail(problem.status >= 400 && problem.status < 500 ? problem.status : 502, {
        error: problem.message || 'Could not save allocations.',
        values
      });
    }
    redirect(
      303,
      `/patients/${event.params.id}/allocations?receipt=${encodeURIComponent(values.receipt)}&saved=1`
    );
  }
};
