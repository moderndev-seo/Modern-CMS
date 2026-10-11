<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { usd, dateTime } from '$lib/modern-practice.js';
  let { data, form } = $props();
  let info = $derived(data.exclusions);
</script>

<svelte:head><title>Duplicate payments · {info.patient_name} | Modern Practice</title></svelte:head>
<div class="mp-page">
  <a href={resolve(asInternalPath(`/patients/${data.patientId}/billing`))}>← Billing review</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Patient finances · USD</p>
      <h1>Review duplicate payments</h1>
      <p>{info.patient_name}</p>
    </div>
  </header>
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration records only
    </p>{/if}
  <p class="mp-notice">
    Exclude a payment only after confirming it records the same money as the payment you retain.
    Equal amounts alone do not prove duplication. No money moves and no invoice is changed.
    Exclusion removes the duplicate from collections and Growth in its original reporting period and
    source. Both records and every decision remain visible.
  </p>
  <p>
    Reverse the duplicate's active match and clear its allocation plan first. Payments with refunds
    cannot be excluded. A payment retained by another active exclusion cannot itself be excluded.
    Restore that duplicate first if the decision was wrong. Restoration includes the payment in
    reporting again; reconcile it afterward.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  {#if data.saved}<p class="mp-success" role="status">
      Decision recorded. Review collections and reconciliation.
    </p>{/if}
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Payment records</h2></div>
    <p class="mp-muted">
      Showing {info.receipts.length} of {info.receipt_count} payments, newest first. The retained-payment
      chooser uses this same list. Reporting uses all included records.
    </p>
    {#each info.receipts as receipt (receipt.id)}
      {@const candidates = info.receipts.filter(
        (other) =>
          other.id !== receipt.id &&
          !other.excluded &&
          Number(other.amount) === Number(receipt.amount)
      )}
      <article class="mp-form">
        <h3>
          {receipt.reference} · {receipt.excluded
            ? 'Excluded duplicate'
            : 'Included in collections'}
        </h3>
        <p>
          {usd(receipt.amount)} · {dateTime(receipt.occurred_at)} · Decision version {receipt.revision}
        </p>
        {#if receipt.blockers.length}
          {#each receipt.blockers as reason (reason)}<p class="mp-notice">{reason}</p>{/each}
        {:else if !receipt.excluded && !candidates.length}
          <p>
            No other included equal-amount payment is available in this list. Nothing is
            automatically identified as a duplicate.
          </p>
        {:else}
          <details open={form?.values?.receipt === receipt.id}>
            <summary>{receipt.excluded ? 'Restore this payment' : 'Exclude as a duplicate'}</summary
            >
            <form method="POST" class="mp-form">
              <input type="hidden" name="receipt" value={receipt.id} />
              <input type="hidden" name="revision" value={receipt.revision} />
              <input type="hidden" name="excluded" value={!receipt.excluded} />
              <input
                type="hidden"
                name="request_id"
                value={form?.values?.receipt === receipt.id
                  ? form.values.request_id
                  : data.requestId}
              />
              {#if !receipt.excluded}
                <label
                  >Payment to retain
                  <select
                    name="retained"
                    required
                    value={form?.values?.receipt === receipt.id ? form.values.retained || '' : ''}
                  >
                    <option value="">Select the record for the same real payment</option>
                    {#each candidates as candidate (candidate.id)}<option value={candidate.id}
                        >{candidate.reference} · {usd(candidate.amount)} · {dateTime(
                          candidate.occurred_at
                        )}</option
                      >{/each}
                  </select>
                </label>
              {/if}
              <label
                >Reason and evidence<textarea
                  name="reason"
                  maxlength="1000"
                  required
                  value={form?.values?.receipt === receipt.id ? form.values.reason : ''}
                ></textarea></label
              >
              <p>
                This records a permanent audit entry. Restoring later does not erase this decision.
              </p>
              <button type="submit" class="mp-button primary"
                >{receipt.excluded
                  ? 'Restore to collections'
                  : 'Exclude duplicate from collections'}</button
              >
            </form>
          </details>
        {/if}
      </article>
    {:else}<p>No payment records yet.</p>{/each}
  </section>
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Decision history</h2></div>
    <p class="mp-muted">
      Showing {info.history.length} of {info.history_count} permanent entries, newest first.
    </p>
    {#each info.history as entry (entry.id)}
      <article class="mp-form">
        <h3>
          {entry.reference} · {entry.excluded ? 'Excluded' : 'Restored'} · Version {entry.revision}
        </h3>
        <p>{usd(entry.amount)} · {dateTime(entry.occurred_at)}</p>
        {#if entry.retained_reference}<p>Retained record: {entry.retained_reference}</p>{/if}
        <p>{entry.reason}</p>
        <p class="mp-muted">Recorded by: {entry.actor}</p>
      </article>
    {:else}<p>No exclusion or restoration decisions recorded.</p>{/each}
  </section>
</div>
