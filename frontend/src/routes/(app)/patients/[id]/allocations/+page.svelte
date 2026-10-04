<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { dateTime } from '$lib/modern-practice.js';
  let { data, form } = $props();
  let extraRows = $state(0);
  let info = $derived(data.allocations);
  let selected = $derived(
    info.receipts.find((/** @type {any} */ row) => row.id === data.selectedReceipt)
  );
  let retry = $derived(form?.values?.receipt === selected?.id ? form?.values : null);
  let lines = $derived(retry?.lines || selected?.lines || []);
  /** @param {number | string} value */
  const money = (value) =>
    Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
</script>

<svelte:head><title>Receipt allocations · {info.patient_name} | Modern Practice</title></svelte:head
>
<div class="mp-page">
  <a href={resolve(asInternalPath(`/patients/${data.patientId}/billing`))}>← Billing review</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Patient finances · USD · All recorded dates</p>
      <h1>Receipt allocations</h1>
      <p>{info.patient_name}</p>
    </div>
  </header>
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration records only
    </p>{/if}
  <p class="mp-notice">
    Distribute existing receipt cash after refunds across this patient's issued USD invoices. This
    does not move money, change Growth, or update invoice paid/due values. Allocations are separate
    from payment-match evidence; never add the two together. No allocation is created automatically
    from a match.
  </p>
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Net cash allocation status</h2></div>
    <div class="mp-form">
      <p>Net collected <strong>USD {money(info.totals.net_collected)}</strong></p>
      <p>Valid allocations <strong>USD {money(info.totals.allocated)}</strong></p>
      <p>Unallocated <strong>USD {money(info.totals.unallocated)}</strong></p>
      <p>Cash needing allocation review <strong>USD {money(info.totals.needs_review)}</strong></p>
      <p class="mp-muted">
        The last three amounts add up to net collected across all receipts. A changed receipt,
        refund, or invoice invalidates the entire affected plan until you review and replace it. No
        automatic proportional refund allocation occurs. These are cash distributions, not amounts
        owed. Invoice overpayments are allowed; credit adjustments and final balances remain
        separate.
      </p>
    </div>
  </section>
  {#if form?.error}<p class="mp-error" role="alert">
      {form.error} Reload before retrying a stale revision.
    </p>{/if}
  {#if data.saved && !form?.error}<p role="status">
      Allocation version saved. Earlier versions remain in history.
    </p>{/if}
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Choose a receipt</h2></div>
    <div class="mp-form">
      <p class="mp-muted">
        Most recent 100 of {info.receipt_count} payment receipts. All records contribute to totals.
      </p>
      {#each info.receipts as receipt (receipt.id)}<article class="mp-followup">
          <a
            href={resolve(
              asInternalPath(`/patients/${data.patientId}/allocations?receipt=${receipt.id}`)
            )}>{receipt.reference}</a
          >
          <p>
            Received USD {money(receipt.gross)} · Remaining after refunds USD {money(receipt.net)} · Version
            {receipt.revision}
          </p>
          <p>
            {receipt.needs_review
              ? 'Needs review — previous allocations are excluded from valid totals.'
              : `Allocated USD ${money(receipt.allocated)}`}
          </p>
        </article>{:else}<p>No payment receipts recorded.</p>{/each}
    </div>
  </section>
  {#if selected}
    <section class="mp-panel">
      <div class="mp-panel-heading pink"><h2>Allocate {selected.reference}</h2></div>
      <div class="mp-form">
        <p>
          Enter the complete replacement plan, not just the change. Use each invoice once. Leave a
          row entirely blank to omit it. Maximum total: USD {money(selected.net)}. Up to 20 invoices
          per receipt.
        </p>
        <p class="mp-muted">
          Invoice chooser: most recent 100 of {info.invoice_count} linked invoices. Only issued USD invoices
          are eligible. History keeps invoice names even if records later change.
        </p>
        <form method="POST" class="mp-form">
          <input type="hidden" name="receipt" value={selected.id} />
          <input type="hidden" name="revision" value={retry?.revision ?? selected.revision} />
          <input type="hidden" name="request_id" value={retry?.request_id || data.requestId} />
          {#each Array.from( { length: Math.min(20, Math.max(2, lines.length) + extraRows) } ) as _, index (index)}
            <div class="mp-columns">
              <label class="mp-field"
                ><span>Invoice {index + 1}</span><select
                  name="invoice"
                  value={lines[index]?.invoice || ''}
                >
                  <option value="">Choose invoice</option>
                  {#if lines[index]?.invoice && !info.invoices.some((/** @type {any} */ i) => i.id === lines[index].invoice && i.eligible)}<option
                      value={lines[index].invoice}
                      >Previous invoice — unavailable; choose another or clear row</option
                    >{/if}
                  {#each info.invoices.filter((/** @type {any} */ i) => i.eligible) as invoice (invoice.id)}<option
                      value={invoice.id}>{invoice.number}</option
                    >{/each}
                </select></label
              >
              <label class="mp-field"
                ><span>Amount {index + 1} · USD</span><input
                  name="amount"
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={lines[index]?.amount || ''}
                /></label
              >
            </div>
          {/each}
          {#if Math.max(2, lines.length) + extraRows < 20}<button
              type="button"
              class="mp-button"
              onclick={() => (extraRows += 1)}>Add invoice row</button
            >{/if}
          <label class="mp-field"
            ><span>Reason for allocation change</span><textarea
              name="reason"
              required
              maxlength="1000"
              value={retry?.reason || ''}></textarea></label
          >
          <button class="mp-button primary" type="submit">Save complete allocation</button>
          <button class="mp-button" type="submit" name="clear" value="1" formnovalidate
            >Clear allocations with this reason</button
          >
          <p class="mp-muted">
            Clearing creates an empty version; it preserves prior history and returns all remaining
            cash to unallocated. A reason is still required.
          </p>
        </form>
      </div>
    </section>
  {/if}
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Valid allocations by invoice</h2></div>
    <div class="mp-form">
      {#each Object.entries(info.by_invoice) as [id, value] (id)}<p>
          {info.invoices.find((/** @type {any} */ i) => i.id === id)?.number || id}: USD {money(
            /** @type {number} */ (value)
          )}
        </p>{:else}<p>No valid allocations recorded.</p>{/each}
    </div>
  </section>
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Allocation history</h2></div>
    <div class="mp-form">
      <p class="mp-muted">
        Latest 100 of {info.history_count} versions · UTC · History is permanent. Only the latest version
        of each receipt may contribute to current totals.
      </p>
      {#each info.history as entry (entry.id)}<article class="mp-followup">
          <h3>{entry.receipt} · Version {entry.revision}</h3>
          <p>{entry.reason}</p>
          <p class="mp-muted">{dateTime(entry.at)} · {entry.actor}</p>
          {#each entry.lines as line (line.invoice)}<p>
              {entry.invoices[line.invoice]?.number || line.invoice}: USD {money(line.amount)}
            </p>{:else}<p>Allocations cleared.</p>{/each}
        </article>{:else}<p>No allocation history.</p>{/each}
    </div>
  </section>
</div>
