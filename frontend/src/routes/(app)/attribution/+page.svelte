<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  let { data, form } = $props();
</script>

<svelte:head><title>Attribution connections | Modern Practice</title></svelte:head>
<div class="mp-page">
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Closed-loop attribution · Sandbox</p>
      <h1>Attribution connections</h1>
      <p>Trace each imported event to its patient and recorded revenue.</p>
    </div>
  </header>
  <p class="mp-notice">
    <strong>Test foundation — no live providers connected.</strong> Google Ads, GA4, website forms, booking
    and payment connectors are not enabled. Sandbox events are fictional assertions, not verified transactions.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  {#if data.info.can_write}
    <form method="POST" action="?/create" class="mp-panel mp-form">
      <h2>Create a fictional test connection</h2>
      <p>
        Each connection keeps its external patient and event IDs separate. Demo records will
        contribute to this TEST practice’s Patients and Growth.
      </p>
      <input type="hidden" name="request_id" value={data.requestKey} />
      <label
        >Connection name<input
          name="name"
          required
          maxlength="100"
          placeholder="TEST website and payments"
        /></label
      >
      <button class="mp-button">Create test connection</button>
    </form>
  {:else}<p class="mp-notice">
      Select a practice whose name starts with TEST - to rehearse intake with fictional records.
    </p>{/if}
  <section class="mp-panel">
    <h2>Test connections</h2>
    {#each data.info.connections as item (item.id)}<p>
        <a href={resolve(asInternalPath(`/attribution/${item.id}`))}>{item.name}</a> · Sandbox
      </p>{:else}<p>No connections yet. No automatic tracking is active.</p>{/each}
  </section>
  <section class="mp-panel">
    <h2>What this foundation verifies</h2>
    <p>
      Stable patient links, preserved first touch, duplicate-event protection, payment/refund
      reconciliation and practice isolation. Booking events record an imported outcome; they do not
      create a calendar appointment.
    </p>
    <p>
      Unknown sources stay Unknown. Missing spend leaves ROAS unavailable. This records attribution
      evidence; it does not establish that marketing caused incremental revenue.
    </p>
  </section>
</div>
