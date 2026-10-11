<script>
  import { resolve } from '$app/paths';
  import { sources, sourceLabel, usd } from '$lib/modern-practice.js';
  let { data, form } = $props();
  let report = $derived(data.report);
  const today = new Date().toISOString().slice(0, 10);
</script>

<svelte:head><title>Growth | Modern Practice</title></svelte:head>
<div class="mp-page">
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">From marketing spend to patient revenue</p>
      <h1>Growth</h1>
      <p class="mp-muted">Actual care. Actual collections. Attributed to the first touch.</p>
    </div>
    <a class="mp-button secondary" href={resolve('/patients')}>View patients →</a>
  </header>
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demo reporting period: September 1–30, 2026
    </p>{/if}
  <form class="mp-range" method="GET">
    <label
      >From · UTC<input
        type="date"
        name="start"
        required
        value={report?.start || data.start}
      /></label
    ><label
      >Through · UTC<input type="date" name="end" required value={report?.end || data.end} /></label
    ><button class="mp-button">Apply dates</button><span class="mp-muted"
      >Inclusive calendar dates · all amounts USD</span
    >
  </form>
  {#if data.rangeError}<p class="mp-error" role="alert">
      {data.rangeError} Choose a valid date range and apply it again.
    </p>{/if}
  {#if report}
    {@const totals = report.totals}
    <div class="mp-metrics">
      <article class="mp-metric dark">
        <span>Net collected revenue</span><strong>{usd(totals.net_revenue)}</strong><small
          >{usd(totals.payments)} received − {usd(totals.refunds)} refunded</small
        >
      </article>
      <article class="mp-metric">
        <span>Leads</span><strong>{totals.leads}</strong><small>New patient journeys</small>
      </article>
      <article class="mp-metric">
        <span>Booked appointments</span><strong>{totals.booked}</strong><small
          >Distinct patients booked</small
        >
      </article>
      <article class="mp-metric">
        <span>Treated patients</span><strong>{totals.treated}</strong><small
          >Distinct patients treated</small
        >
      </article>
      <article class="mp-metric accent">
        <span>Recorded marketing spend</span><strong>{usd(totals.spend)}</strong><small
          >ROAS {totals.roas === null ? 'unavailable' : Number(totals.roas).toFixed(2) + '×'}</small
        >
      </article>
    </div>
    {#if totals.missing_spend_sources.length}<p class="mp-notice">
        Spend has not been entered for {totals.missing_spend_sources.join(', ')}. Recorded spend may
        be incomplete; total ROAS is unavailable.
      </p>{/if}
    <section class="mp-panel">
      <div class="mp-panel-heading pink">
        <h2>Revenue by original source</h2>
        <span class="mp-badge">First touch</span>
      </div>
      <div class="mp-table-wrap">
        <table class="mp-table">
          <thead
            ><tr
              ><th>Source</th><th>Leads</th><th>Booked</th><th>Treated</th><th>Net collected</th><th
                >Entered spend</th
              ><th>ROAS</th></tr
            ></thead
          ><tbody
            >{#each report.sources as row (row.source)}<tr
                ><td><strong>{row.label}</strong></td><td>{row.leads}</td><td>{row.booked}</td><td
                  >{row.treated}</td
                ><td class="mp-money">{usd(row.net_revenue)}</td><td>{usd(row.spend)}</td><td
                  >{#if row.roas !== null}<strong
                      class:mp-positive={Number(row.roas) >= 0}
                      class:mp-negative={Number(row.roas) < 0}
                      >{Number(row.roas).toFixed(2)}×</strong
                    >{:else}<span class="mp-muted"
                      >{row.spend === null ? 'Missing spend' : 'N/A · $0 spend'}</span
                    >{/if}</td
                ></tr
              >{/each}</tbody
          >
        </table>
      </div>
    </section>
    <div class="mp-columns">
      <section class="mp-panel">
        <div class="mp-panel-heading"><h2>How to read this report</h2></div>
        <div class="mp-form mp-rules">
          <p>
            <strong>Activity dates, not a cohort funnel.</strong> Leads use the known-lead timestamp.
            Booked and treated count distinct patients with that event in the range. Repeat events do
            not count the same patient twice. These counts may refer to different people.
          </p>
          <p>
            <strong>Cash basis.</strong> Payments and refunds use their own received/refunded timestamps,
            from 00:00 UTC on the start date to 00:00 UTC the day after the end date. A refund in this
            period reduces this period, even if the payment was earlier. Duplicate-payment exclusions
            and restorations, and audited amount corrections, restate the receipt’s original period, so
            past totals can change; they are not new cash on the correction date.
          </p>
          <p>
            <strong>First-touch attribution.</strong> All net receipts go to the patient's immutable original
            source, regardless of when the lead arrived or whether later touches use another channel.
            Missing sources stay Unknown. Invoice totals and deal values are excluded.
          </p>
          <p>
            <strong>ROAS = net collected revenue ÷ entered spend.</strong> Daily spend entries are summed
            within the range. Missing spend is never assumed to be zero. Explicit $0 has no defined ROAS.
            Enter all applicable daily spend before interpreting the ratio; partial entries are not automatically
            detected.
          </p>
        </div>
      </section>
      <section class="mp-panel">
        <div class="mp-panel-heading">
          <h2>Enter marketing spend</h2>
          <span class="mp-badge">Manual</span>
        </div>
        {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}{#if form?.success}<p
            class="mp-success"
            role="status"
          >
            Spend saved. Totals reflect the selected date range.
          </p>{/if}{#if data.role === 'ADMIN'}<form
            class="mp-form"
            method="POST"
            action={`?/spend&start=${report.start}&end=${report.end}`}
          >
            <p class="mp-muted">
              One total per source per UTC day. Saving the same source and date replaces that day's
              amount. Enter $0 only when zero spend is confirmed.
            </p>
            <label
              >Source<select name="source" value={form?.values?.source || 'google_ads'}
                >{#each sources as [key, label] (key)}<option value={key}>{label}</option
                  >{/each}</select
              ></label
            >
            <div class="mp-form-grid">
              <label
                >Date · UTC<input
                  type="date"
                  name="date"
                  required
                  max={today}
                  value={form?.values?.date || (report.end > today ? today : report.end)}
                /></label
              ><label
                >Daily spend · USD<input
                  type="number"
                  name="amount"
                  min="0"
                  step="0.01"
                  max="9999999999.99"
                  required
                  value={form?.values?.amount || ''}
                /></label
              >
            </div>
            <button class="mp-button">Save daily spend</button>
          </form>{:else}<p class="mp-form mp-muted">
            A practice administrator can enter marketing spend.
          </p>{/if}
        <details class="mp-form">
          <summary>Saved entries in this range ({report.spend_entries.length})</summary
          >{#each report.spend_entries as entry (`${entry.source}:${entry.date}`)}<p>
              {entry.date} · {sourceLabel(entry.source)} · {usd(entry.amount)}
            </p>{:else}<p>No spend entered in this period.</p>{/each}
        </details>
      </section>
    </div>
  {/if}
</div>
