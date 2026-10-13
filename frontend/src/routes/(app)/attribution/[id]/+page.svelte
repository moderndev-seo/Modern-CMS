<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { dateTime } from '$lib/modern-practice.js';
  let { data, form } = $props();
  let info = $derived(data.info);
</script>

<svelte:head><title>Attribution evidence | Modern Practice</title></svelte:head>
<div class="mp-page">
  <a href={resolve('/attribution')}>All attribution connections</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Sandbox event history</p>
      <h1>{info.connection.name}</h1>
      <p>Every accepted event links back to the same patient journey.</p>
    </div>
  </header>
  <p class="mp-notice">
    <strong>Fictional test data only.</strong> This is not a live vendor connection or proof of bank settlement.
    Failed requests are returned to the caller, not stored in a retry queue.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  {#if form?.success}<p class="mp-notice" role="status">{form.success}</p>{/if}
  <form method="POST" action="?/demo" class="mp-panel mp-form">
    <h2>Rehearse the complete loop</h2>
    <p>
      Creates one fictional patient and eight September 2026 events: introduction, later touch,
      booking, attendance, consultation, treatment, payment and refund. These count in this TEST
      practice’s Growth. Running again reuses the same event IDs and does not add duplicate cash.
    </p>
    <button class="mp-button">Run or resume fictional demo</button>
  </form>
  <section class="mp-panel">
    <h2>Accepted events ({info.count})</h2>
    <p>
      Newest received first · 50 per page · times in UTC. Follow a patient link for chronological
      activity and current cash after corrections.
    </p>
    <div style="overflow-x:auto">
      <table class="mp-table">
        <thead
          ><tr
            ><th>External event</th><th>Type</th><th>Evidence</th><th>Received</th><th>Journey</th
            ></tr
          ></thead
        ><tbody>
          {#each info.results as row (row.id)}<tr
              ><td>{row.event_id}</td><td>{row.kind}</td><td>Sandbox</td><td
                >{dateTime(row.received_at)}</td
              ><td
                ><a href={resolve(asInternalPath(`/patients/${row.patient_id}`))}>Open patient</a
                ></td
              ></tr
            >{:else}<tr><td colspan="5">No accepted events yet.</td></tr>{/each}
        </tbody>
      </table>
    </div>
    <nav aria-label="Event pages">
      {#if info.page > 1}<a
          href={resolve(asInternalPath(`/attribution/${info.connection.id}?page=${info.page - 1}`))}
          >Previous</a
        >{/if} <span>Page {info.page}</span>
      {#if info.page * info.page_size < info.count}<a
          href={resolve(asInternalPath(`/attribution/${info.connection.id}?page=${info.page + 1}`))}
          >Next</a
        >{/if}
    </nav>
  </section>
  <p>
    <a href={resolve(asInternalPath('/growth?start=2026-09-01&end=2026-09-30'))}
      >Review September Growth</a
    > · Growth includes all records in the practice, not just this connection. First-touch source gets
    the revenue; later email touches do not overwrite it. Spend remains manual.
  </p>
</div>
