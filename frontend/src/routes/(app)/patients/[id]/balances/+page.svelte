<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  let { data } = $props();
  let balance = $derived(data.balances);
  /** @param {number | string | null} value */
  const money = (value) =>
    value === null
      ? 'Unavailable'
      : `USD ${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
</script>

<svelte:head
  ><title>Recorded balances · {balance.patient_name} | Modern Practice</title></svelte:head
>
<div class="mp-page">
  <a href={resolve(asInternalPath(`/patients/${data.patientId}/billing`))}>← Billing review</a>
  <a href={resolve(asInternalPath(`/patients/${data.patientId}/allocations`))}
    >Reconcile allocations and refunds →</a
  >
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Patient finances · All recorded dates</p>
      <h1>Recorded balances</h1>
      <p>{balance.patient_name}</p>
    </div>
  </header>
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration records only
    </p>{/if}
  <p class="mp-notice">
    Balances use issued USD invoices less active charge credits and explicitly allocated net receipt
    cash. Refunds already reduce that cash; explained refunds below are not subtracted again. Legacy
    invoice-payment entries are reconciliation evidence, never additional cash. This does not change
    invoice fields or verify bank settlement, insurance responsibility, unrecorded charges, or
    unrecorded payments.
  </p>
  {#if !balance.available}
    <section class="mp-panel">
      <div class="mp-panel-heading"><h2>Balance unavailable — reconciliation required</h2></div>
      <div class="mp-form">
        <ul>
          {#each balance.blockers as reason (reason)}<li>{reason}</li>{/each}
        </ul>
        <p>
          Every numeric balance is withheld until these checks pass. Unavailable does not mean zero.
        </p>
      </div>
    </section>
  {:else}
    <section class="mp-panel">
      <div class="mp-panel-heading pink"><h2>Reconciled recorded balance · USD</h2></div>
      <div class="mp-form">
        <p>Adjusted billed <strong>{money(balance.totals.adjusted_billed)}</strong></p>
        <p>Net cash allocated <strong>{money(balance.totals.net_allocated)}</strong></p>
        <p>Outstanding across invoices <strong>{money(balance.totals.outstanding)}</strong></p>
        <p>Overpaid across invoices <strong>{money(balance.totals.overpaid)}</strong></p>
        <p>Net recorded balance <strong>{money(balance.totals.recorded_balance)}</strong></p>
        <p class="mp-muted">
          Net recorded balance is outstanding less overpaid: positive means net outstanding;
          negative means a net overpayment in these records. Invoice overpayments are shown
          separately and are not automatically transferred or refunded.
        </p>
      </div>
    </section>
  {/if}
  <section class="mp-panel">
    <div class="mp-panel-heading"><h2>Invoice reconciliation</h2></div>
    <div class="mp-form">
      <p class="mp-muted">
        All issued linked invoices; {balance.excluded_invoice_count} Draft, Pending or Cancelled invoices
        excluded. No currency conversion. Credits and allocation amounts below are evidence; numeric balances
        appear only when the patient's reconciliation checks pass.
      </p>
      {#each balance.invoices as invoice (invoice.id)}<article class="mp-followup">
          <h3>{invoice.number} · {invoice.currency}</h3>
          {#if invoice.currency === 'USD'}
            <p>
              Original billed {money(invoice.original_billed)} · Active charge credits {money(
                invoice.active_credits
              )} · Adjusted billed {money(invoice.adjusted_billed)}
            </p>
            <p>
              Valid net cash allocated {money(invoice.net_allocated)} · Explained refunds {money(
                invoice.explained_refunds
              )} (already deducted from receipt cash)
            </p>
          {:else}<p>Foreign-currency invoice — USD reconciliation unavailable.</p>{/if}
          <p>Recorded balance <strong>{money(invoice.recorded_balance)}</strong></p>
          <p>Outstanding {money(invoice.outstanding)} · Overpaid {money(invoice.overpaid)}</p>
        </article>{:else}<p>No issued invoices linked to this patient.</p>{/each}
    </div>
  </section>
</div>
