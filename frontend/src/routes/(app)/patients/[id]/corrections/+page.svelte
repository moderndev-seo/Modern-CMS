<script>
  import FinancialPages from '$lib/components/modern-practice/FinancialPages.svelte';
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { usd, dateTime } from '$lib/modern-practice.js';
  let { data, form } = $props();
  let info = $derived(data.corrections);
</script>

<svelte:head><title>Cash corrections · {info.patient_name} | Modern Practice</title></svelte:head>
<div class="mp-page">
  <a href={resolve(asInternalPath(`/patients/${data.patientId}/billing`))}>← Billing review</a>
  <a href={resolve(asInternalPath(`/patients/${data.patientId}/allocations`))}
    >Review allocations →</a
  >
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Patient finances · USD</p>
      <h1>Correct recorded cash details</h1>
      <p>{info.patient_name}</p>
    </div>
  </header>
  <FinancialPages pages={info.pages} />
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration records only
    </p>{/if}
  <p class="mp-notice">
    Correct an incorrectly entered amount, reference or date, one field at a time. No money is
    collected or refunded. Amount changes recalculate the original reporting period and source.
    Reference changes leave collections and reporting dates unchanged. Every prior value, reason,
    administrator and time remain in history. Old references stay reserved to prevent duplicate
    entry. Date corrections move cash between UTC reporting periods; lifetime collections and
    original marketing source stay unchanged. Refunds cannot precede their payment, and cash dates
    cannot be in the future. Patient links cannot be changed here.
  </p>
  <p>
    Reverse the original payment's active match and clear its allocation plan, including refund
    explanations, before correcting a payment or any of its refunds. Reconcile again after saving.
    To undo a correction, enter the previous value as a new correction with a reason. Amounts must
    remain positive and within refund limits; use Billing review → Review duplicate payments to
    exclude an eligible duplicate without deleting it.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  {#if data.saved}<p class="mp-success" role="status">
      Correction recorded. Review updated collections and reconcile billing again.
    </p>{/if}
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Recorded cash</h2></div>
    <p class="mp-muted">
      Showing {info.receipts.length} of {info.receipt_count} records, newest first. Reporting uses all
      records.
    </p>
    {#each info.receipts as receipt (receipt.id)}
      <article class="mp-form">
        <h3>{receipt.reference} · {receipt.kind}</h3>
        <p>
          Current amount <strong>{usd(receipt.amount)}</strong> · {dateTime(receipt.occurred_at)} · Correction
          version {receipt.revision}
        </p>
        {#if receipt.blockers.length}
          {#each receipt.blockers as reason (reason)}<p class="mp-notice">{reason}</p>{/each}
        {:else}
          <details>
            <summary>Correct this amount</summary>
            <form method="POST" class="mp-form">
              <input type="hidden" name="receipt" value={receipt.id} />
              <input type="hidden" name="revision" value={receipt.revision} />
              <input
                type="hidden"
                name="request_id"
                value={form?.values?.receipt === receipt.id
                  ? form.values.request_id
                  : data.requestId}
              />
              <label
                >Correct amount (USD)
                <input
                  name="amount"
                  type="number"
                  min="0.01"
                  max="9999999999.99"
                  step="0.01"
                  required
                  value={form?.values?.receipt === receipt.id ? form.values.amount : receipt.amount}
                />
              </label>
              <label
                >Reason for correction
                <textarea
                  name="reason"
                  maxlength="1000"
                  required
                  value={form?.values?.receipt === receipt.id ? form.values.reason : ''}></textarea>
              </label>
              <button type="submit" class="mp-button primary">Save amount correction</button>
            </form>
          </details>
          <details open={form?.values?.receipt === receipt.id && !!form?.values?.reference}>
            <summary>Correct this reference</summary>
            <form method="POST" class="mp-form">
              <input type="hidden" name="receipt" value={receipt.id} />
              <input type="hidden" name="revision" value={receipt.revision} />
              <input
                type="hidden"
                name="request_id"
                value={form?.values?.receipt === receipt.id
                  ? form.values.request_id
                  : data.requestId}
              />
              <label
                >Correct reference
                <input
                  name="reference"
                  maxlength="100"
                  required
                  value={form?.values?.receipt === receipt.id && form.values.reference !== undefined
                    ? form.values.reference
                    : receipt.reference}
                />
              </label>
              <label
                >Reason for reference correction
                <textarea
                  name="reason"
                  maxlength="1000"
                  required
                  value={form?.values?.receipt === receipt.id && form.values.reference !== undefined
                    ? form.values.reason
                    : ''}></textarea>
              </label>
              <p>
                Amount and date stay unchanged. Previous references remain reserved for this
                receipt, even after restoration.
              </p>
              <button type="submit" class="mp-button primary">Save reference correction</button>
            </form>
          </details>
          <details open={form?.values?.receipt === receipt.id && !!form?.values?.occurred_at}>
            <summary>Correct this date</summary>
            <form method="POST" class="mp-form">
              <input type="hidden" name="receipt" value={receipt.id} />
              <input type="hidden" name="revision" value={receipt.revision} />
              <input
                type="hidden"
                name="request_id"
                value={form?.values?.receipt === receipt.id
                  ? form.values.request_id
                  : data.requestId}
              />
              <label
                >Correct date and time (UTC)
                <input
                  name="occurred_at"
                  type="datetime-local"
                  step="1"
                  required
                  value={form?.values?.receipt === receipt.id && form.values.occurred_at
                    ? form.values.occurred_at.replace(/Z$/, '')
                    : new Date(receipt.occurred_at).toISOString().slice(0, 19)}
                />
              </label>
              <label
                >Reason for date correction
                <textarea
                  name="reason"
                  maxlength="1000"
                  required
                  value={form?.values?.receipt === receipt.id && form.values.occurred_at
                    ? form.values.reason
                    : ''}></textarea>
              </label>
              <p>
                This restates cash in the corrected reporting period. Amount and original marketing
                attribution remain unchanged.
              </p>
              <button type="submit" class="mp-button primary">Save date correction</button>
            </form>
          </details>
        {/if}
      </article>
    {:else}<p>No cash records yet.</p>{/each}
  </section>
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Correction history</h2></div>
    <p class="mp-muted">
      Showing {info.history.length} of {info.history_count} permanent entries, newest first. Restoring
      a value does not erase earlier corrections.
    </p>
    {#each info.history as entry (entry.id)}
      <article class="mp-form">
        <h3>{entry.reference} · Version {entry.revision}</h3>
        {#if entry.field === 'occurred_at'}
          <p>
            Date: {dateTime(entry.before_date)} → {dateTime(entry.after_date)} · Recorded {dateTime(
              entry.occurred_at
            )}
          </p>
        {:else if entry.field === 'reference'}
          <p>
            Reference: {entry.before_reference} → {entry.after_reference} · {dateTime(
              entry.occurred_at
            )}
          </p>
        {:else}<p>{usd(entry.before)} → {usd(entry.after)} · {dateTime(entry.occurred_at)}</p>{/if}
        <p>{entry.reason}</p>
        <p class="mp-muted">Recorded by: {entry.actor}</p>
      </article>
    {:else}<p>No cash corrections recorded.</p>{/each}
  </section>
</div>
