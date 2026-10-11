<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { usd, dateTime } from '$lib/modern-practice.js';
  let { data } = $props();
  let info = $derived(data.statement);
</script>

<svelte:head
  ><title>Internal financial statement · {info.patient_name} | Modern Practice</title></svelte:head
>
<div class="mp-page">
  <a href={resolve(asInternalPath(`/patients/${info.patient_id}/billing`))}>← Billing review</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">{info.practice} · All recorded dates · USD</p>
      <h1>Internal financial statement</h1>
      <p>{info.patient_name} · Generated {dateTime(info.generated_at)}</p>
    </div>
  </header>
  {#if info.practice.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration records only
    </p>{/if}
  <p class="mp-notice">{info.notice}</p>
  <p>
    Generated from current stored records. This is not a locked accounting close. Refresh after
    financial changes; exports remain snapshots of their generation time.
  </p>
  <a
    class="mp-button"
    data-sveltekit-reload
    href={resolve(asInternalPath(`/patients/${info.patient_id}/statement/export.csv`))}
    >Download internal statement CSV</a
  >
  <section class="mp-panel mp-form">
    <h2>Recorded collections</h2>
    <p>Net collected: <strong>{usd(info.cash.net_collected)}</strong></p>
    <p>
      Allocated: {usd(info.cash.allocated)} · Unallocated: {usd(info.cash.unallocated)} · Needs review:
      {usd(info.cash.needs_review)}
    </p>
    {#if info.available}
      <p>
        Adjusted billed: {usd(info.totals.adjusted_billed)} · Recorded balance:
        <strong>{usd(info.totals.recorded_balance)}</strong>
      </p>
    {:else}<h3>Recorded balance unavailable</h3>
      <ul>
        {#each info.blockers as reason (reason)}<li>{reason}</li>{/each}
      </ul>{/if}
  </section>
  <section class="mp-panel mp-form">
    <h2>Issued invoices and internal credits</h2>
    {#each info.invoices as invoice (invoice.id)}
      <article>
        <h3>{invoice.number} · {invoice.currency}</h3>
        <p>Original billed: {invoice.currency} {invoice.original_billed}</p>
        <p>
          Active internal credits: {invoice.active_credits === null
            ? 'Unavailable'
            : usd(invoice.active_credits)} · Adjusted billed: {invoice.adjusted_billed === null
            ? 'Unavailable'
            : usd(invoice.adjusted_billed)}
        </p>
        <p>
          Net allocated cash: {invoice.net_allocated === null
            ? 'Unavailable'
            : usd(invoice.net_allocated)} · Recorded balance: {invoice.recorded_balance === null
            ? 'Unavailable'
            : usd(invoice.recorded_balance)}
        </p>
      </article>
    {:else}<p>No issued invoices.</p>{/each}
    <p>
      {info.excluded_invoice_count} draft, pending or cancelled invoices excluded from billed figures.
    </p>
  </section>
  <section class="mp-panel mp-form">
    <h2>Permanent credit history</h2>
    {#each info.credits as credit (credit.id)}
      <article>
        <h3>
          {credit.invoice} · {credit.reversal_of
            ? 'Credit reversed'
            : credit.reversed
              ? 'Credit (since reversed)'
              : 'Internal credit'} · {usd(credit.amount)}
        </h3>
        <p>{credit.reason}</p>
        <p>{credit.actor} · {dateTime(credit.at)}</p>
      </article>
    {:else}<p>No internal credits recorded.</p>{/each}
    <p>
      The CSV also includes all cash records, cash corrections and duplicate-payment decisions. Both
      this page and its download require practice administrator access.
    </p>
  </section>
</div>
