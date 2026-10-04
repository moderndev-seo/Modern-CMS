<script>
  import { resolve } from '$app/paths';
  import { dateTime } from '$lib/modern-practice.js';
  import { asInternalPath } from '$lib/utils/paths.js';
  let { data, form } = $props();
  let billing = $derived(data.billing);
  let coverage = $derived(billing.receipt_coverage);
  /** @param {string | number} value */
  const amount = (value) =>
    Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
</script>

<svelte:head><title>Billing review · {billing.patient_name} | Modern Practice</title></svelte:head>
<div class="mp-page">
  <a href={resolve(asInternalPath(`/patients/${billing.patient_id}`))}>← Patient journey</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Patient finances · All recorded dates</p>
      <h1>Billing review</h1>
      <p>{billing.patient_name}</p>
    </div>
  </header>
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration records only
    </p>{/if}
  <p class="mp-notice">
    Invoice payments and patient receipts are separate records. Match existing records only when you
    have verified they represent the same payment. Matching does not create money, change Growth, or
    allocate refunds. Never add these two ledgers together.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  <div class="mp-columns">
    <section class="mp-panel">
      <div class="mp-panel-heading pink"><h2>Patient collections · USD</h2></div>
      <div class="mp-form">
        <p>Received payments <strong>USD {amount(billing.payments)}</strong></p>
        <p>Refunds <strong>USD {amount(billing.refunds)}</strong></p>
        <p>Net collected <strong>USD {amount(billing.net_collected)}</strong></p>
        <p class="mp-muted">
          These patient receipts drive Growth. This view includes all receipt dates; Growth applies
          its selected date range. No invoice amount is added to collected revenue.
        </p>
      </div>
    </section>
    <section class="mp-panel">
      <div class="mp-panel-heading"><h2>Invoice records by currency</h2></div>
      <div class="mp-form">
        {#each billing.currencies as row (row.currency)}<article class="mp-followup">
            <h3>{row.currency}</h3>
            <p>Billed <strong>{amount(row.billed)}</strong></p>
            <p>Invoice payment entries <strong>{amount(row.invoice_payments)}</strong></p>
          </article>{:else}<p>
            No invoices linked to this patient's contact. Patient receipts remain available
            independently.
          </p>{/each}
        <p class="mp-muted">
          Billed includes Sent, Viewed, Partially Paid, Overdue and Paid invoices. Draft, Pending
          and Cancelled invoices are excluded ({billing.excluded_from_billed_count}). Invoice
          payment entries include all statuses. Currencies are never combined or converted.
        </p>
      </div>
    </section>
  </div>
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Receipt-to-invoice coverage · USD</h2></div>
    <div class="mp-form">
      <p>
        All recorded dates and all receipts, including records beyond the lists below. Refunds
        follow their original receipt through its active, unchanged payment match.
      </p>
      {#each [{ key: 'linked', label: 'Linked through valid matches' }, { key: 'unmatched', label: 'No active match' }, { key: 'needs_review', label: 'Changed match — needs review' }] as group (group.key)}
        <article class="mp-followup">
          <h3>{group.label}</h3>
          <p>
            {coverage[group.key].payment_count} payment receipts · Received USD {amount(
              coverage[group.key].payments
            )} · Refunds USD {amount(coverage[group.key].refunds)} · Net USD {amount(
              coverage[group.key].net_collected
            )}
          </p>
        </article>
      {/each}
      <p class="mp-muted">
        These groups partition patient collections; they are not additional revenue. A changed or
        reversed match contributes nothing to linked totals. Refunds shown here do not issue an
        invoice credit or change invoice paid/due values. Final patient balances and split
        allocations are not implemented. Charge credits are recorded separately below.
      </p>
    </div>
  </section>
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Match existing payments</h2></div>
    <form class="mp-form" method="POST" action="?/match">
      <p>
        One receipt to one invoice payment, equal amounts in USD, for this patient. Use the original
        payment amount even if a separate refund exists. Verify dates and references yourself; equal
        amounts alone do not prove a match.
      </p>
      <p class="mp-muted">
        Showing up to the 100 most recent eligible entries from each ledger. Unmatched receipts: {billing
          .matching.receipt_count}; unmatched invoice payments: {billing.matching.payment_count}.
        Match history is permanent. Reverse a mistaken match below before matching its records
        again.
      </p>
      {#if billing.matching.receipts.length && billing.matching.invoice_payments.length}
        <label
          >Patient payment receipt<select name="receipt" required
            ><option value="">Select receipt</option
            >{#each billing.matching.receipts as receipt (receipt.id)}<option
                value={receipt.id}
                selected={form?.values?.receipt === receipt.id}
                >{receipt.reference} · USD {amount(receipt.amount)} · {receipt.at.slice(
                  0,
                  10
                )}</option
              >{/each}</select
          ></label
        >
        <label
          >Invoice payment<select name="invoice_payment" required
            ><option value="">Select invoice payment</option
            >{#each billing.matching.invoice_payments as payment (payment.id)}<option
                value={payment.id}
                selected={form?.values?.invoice_payment === payment.id}
                >{payment.invoice} · {payment.reference || 'No reference'} · USD {amount(
                  payment.amount
                )} · {payment.date}</option
              >{/each}</select
          ></label
        >
        <label
          >Reason / evidence<textarea
            name="reason"
            rows="3"
            required
            maxlength="1000"
            value={form?.action === 'matches' ? form?.values?.reason || '' : ''}></textarea></label
        >
        <button class="mp-button">Confirm payment match</button>
      {:else}<p>
          No eligible pair is available. Review existing records before recording any new payment;
          this screen does not import or create payments.
        </p>{/if}
    </form>
  </section>
  <section class="mp-panel">
    <div class="mp-panel-heading">
      <h2>Payment match history</h2>
      <span>{billing.matching.match_count} total</span>
    </div>
    <div class="mp-form">
      <p class="mp-muted">
        Most recent 100 matches · UTC · Refunds remain separate and are not reconciled here.
      </p>
      {#each billing.matching.matches as match (match.id)}<article class="mp-followup">
          <strong>{match.receipt} · USD {amount(match.amount)}</strong>
          <p>{match.reason}</p>
          <a href={resolve(asInternalPath(`/invoices/${match.invoice}`))}>View matched invoice →</a>
          <p class="mp-muted">{dateTime(match.at)} · {match.actor}</p>
          {#if match.reversal}
            <p>
              <strong>Reversed</strong> · {dateTime(match.reversal.at)} · {match.reversal.actor}
            </p>
            <p>{match.reversal.reason}</p>
            <p class="mp-muted">
              Historical match only. See newer history entries for any later match.
            </p>
          {:else}
            <p>
              <strong>Active match</strong> · {match.consistent
                ? 'Matched records still agree.'
                : 'Needs review: an underlying record changed after matching. No automatic correction was made.'}
            </p>
            <details open={form?.values?.match === match.id}>
              <summary>Correct this match</summary>
              <form class="mp-form" method="POST" action="?/reverse">
                <input type="hidden" name="match" value={match.id} />
                <p>
                  Reversing releases both records for matching again. It keeps the original history
                  and does not refund money, delete payments, or change Growth.
                </p>
                <label
                  >Reason for reversal<textarea
                    name="reason"
                    rows="2"
                    required
                    maxlength="1000"
                    value={form?.values?.match === match.id ? form?.values?.reason || '' : ''}
                  ></textarea></label
                >
                <button class="mp-button">Confirm match reversal</button>
              </form>
            </details>
          {/if}
        </article>{:else}<p>No matches recorded.</p>{/each}
    </div>
  </section>
  <section class="mp-panel">
    <div class="mp-panel-heading">
      <h2>Linked invoices</h2>
      <span>{billing.count} total</span>
    </div>
    <div class="mp-form">
      <p class="mp-muted">
        {billing.scope} Stored paid/due values below belong to the existing invoice ledger; they are not
        a calculation of what this patient owes after patient receipts.
      </p>
      {#each billing.results as invoice (invoice.id)}<article class="mp-followup">
          <a href={resolve(asInternalPath(`/invoices/${invoice.id}`))}
            ><strong>{invoice.number} · {invoice.title}</strong></a
          >
          <p>
            {invoice.status.replaceAll('_', ' ')} · {invoice.currency}{invoice.included_in_billed
              ? ''
              : ' · Excluded from billed total'}
          </p>
          <p>
            Invoice total: {amount(invoice.total)} · Payment entries: {amount(
              invoice.invoice_payments
            )}
          </p>
          <p>
            Stored paid: {amount(invoice.stored_paid)} · Stored due: {amount(invoice.stored_due)}
          </p>
          {#if invoice.currency === 'USD'}
            {@const linked = coverage.by_invoice[invoice.id]}
            <p>
              Patient receipts linked through valid matches: USD {amount(linked?.payments ?? 0)} · Related
              refunds: USD {amount(linked?.refunds ?? 0)} · Net linked collections: USD {amount(
                linked?.net_collected ?? 0
              )}
            </p>
            <p class="mp-muted">
              {linked
                ? 'Derived from current matches and the original payment on each refund.'
                : 'No patient receipts linked through a valid active match.'} This is not an amount owed
              or proof of bank settlement.
            </p>
          {:else}
            <p class="mp-muted">
              Receipt coverage unavailable for this currency; patient receipts are USD. No
              conversion is performed.
            </p>
          {/if}
          <p>Active charge credits · USD {amount(invoice.credit_adjustment.active_credits)}</p>
          {#if invoice.credit_adjustment.needs_review}
            <p class="mp-error">
              Credit needs review: the invoice changed after a credit was recorded. Adjusted billed
              value is unavailable. Review the credit history before correcting it.
            </p>
          {:else if invoice.credit_adjustment.adjusted_billed !== null}
            <p>
              <strong
                >Adjusted billed value · USD {amount(
                  invoice.credit_adjustment.adjusted_billed
                )}</strong
              >
            </p>
            <p class="mp-muted">
              Original billed value less active charge credits. This is not the amount owed: it does
              not subtract payments or determine whether a refund is due. Original invoice paid/due
              values remain separate.
            </p>
          {:else}
            <p class="mp-muted">
              Adjusted billed value unavailable for this invoice status or currency.
            </p>
          {/if}
          {#if invoice.credit_adjustment.can_credit}
            <details open={form?.action === 'credits' && form?.values?.invoice === invoice.id}>
              <summary>Record charge credit</summary>
              <form class="mp-form" method="POST" action="?/credit">
                <input type="hidden" name="invoice" value={invoice.id} />
                <input
                  type="hidden"
                  name="request_id"
                  value={form?.action === 'credits' && form?.values?.invoice === invoice.id
                    ? form?.values?.request_id
                    : data.creditRequest}
                />
                <p>
                  Record an approved reduction in this invoice's charge. This does not send a credit
                  note, change the original invoice, refund money or reduce Growth revenue.
                </p>
                <label
                  >Credit amount · USD<input
                    name="amount"
                    type="number"
                    min="0.01"
                    max={invoice.credit_adjustment.adjusted_billed}
                    step="0.01"
                    required
                    value={form?.action === 'credits' && form?.values?.invoice === invoice.id
                      ? form?.values?.amount
                      : ''}
                  /></label
                >
                <label
                  >Reason for credit<textarea
                    name="reason"
                    maxlength="1000"
                    required
                    rows="2"
                    value={form?.action === 'credits' && form?.values?.invoice === invoice.id
                      ? form?.values?.reason
                      : ''}></textarea></label
                >
                <button class="mp-button">Confirm charge credit</button>
              </form>
            </details>
          {/if}
          {#if !invoice.ledger_matches_stored_paid}<p class="mp-error">
              Needs review: invoice payment entries differ from its stored paid amount. No automatic
              correction was made.
            </p>{/if}
        </article>{:else}<p>No invoices on this page.</p>{/each}
      <nav class="mp-patient-links" aria-label="Invoice pages">
        {#if billing.page > 1}<a
            href={resolve(
              asInternalPath(`/patients/${billing.patient_id}/billing?page=${billing.page - 1}`)
            )}>← Previous</a
          >{/if}
        {#if billing.page * billing.page_size < billing.count}<a
            href={resolve(
              asInternalPath(`/patients/${billing.patient_id}/billing?page=${billing.page + 1}`)
            )}>Next →</a
          >{/if}
      </nav>
    </div>
  </section>
</div>

<section class="mp-page">
  <section class="mp-panel">
    <div class="mp-panel-heading">
      <h2>Charge credit history</h2>
      <span>{billing.credit_history.count} entries</span>
    </div>
    <div class="mp-form">
      <p class="mp-muted">
        Most recent 100 entries · UTC · Original entries and reversals are permanent. These are
        internal charge adjustments, not cash refunds or issued credit-note documents.
      </p>
      {#each billing.credit_history.entries as credit (credit.id)}
        <article class="mp-followup">
          <strong
            >{credit.invoice} · USD {amount(credit.amount)} · {credit.is_reversal
              ? 'Credit reversal'
              : credit.reversed
                ? 'Reversed credit'
                : 'Charge credit'}</strong
          >
          <p>{credit.reason}</p>
          <p class="mp-muted">{dateTime(credit.at)} · {credit.actor}</p>
          {#if !credit.is_reversal && !credit.reversed}
            <details
              open={form?.action === 'credit-reversals' && form?.values?.credit === credit.id}
            >
              <summary>Reverse this credit</summary>
              <form class="mp-form" method="POST" action="?/reverseCredit">
                <input type="hidden" name="credit" value={credit.id} />
                <input
                  type="hidden"
                  name="request_id"
                  value={form?.action === 'credit-reversals' && form?.values?.credit === credit.id
                    ? form?.values?.request_id
                    : data.reversalRequest}
                />
                <p>
                  This reverses the full charge credit and preserves its history. It does not
                  collect money or change Growth.
                </p>
                <label
                  >Reason for credit reversal<textarea
                    name="reason"
                    maxlength="1000"
                    required
                    rows="2"
                    value={form?.action === 'credit-reversals' && form?.values?.credit === credit.id
                      ? form?.values?.reason
                      : ''}></textarea></label
                >
                <button class="mp-button">Confirm credit reversal</button>
              </form>
            </details>
          {/if}
        </article>
      {:else}<p>No charge credits recorded.</p>{/each}
    </div>
  </section>
</section>
