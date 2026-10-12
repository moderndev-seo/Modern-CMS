<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { dateTime, nowInput } from '$lib/modern-practice.js';
  import RecordPages from '$lib/components/modern-practice/RecordPages.svelte';
  let { data, form } = $props();
  let info = $derived(data.info);
  const average = (value) => (value === null ? 'Not available' : Number(value).toFixed(1));
  const label = (options, value) => options.find(([key]) => key === value)?.[1] || value;
</script>

<svelte:head><title>Reviews | Modern Practice</title></svelte:head>
<div class="mp-page">
  {#if data.org?.name?.startsWith('TEST -')}<p class="mp-demo">
      {data.org.name} · Fictional demonstration records only
    </p>{/if}
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Your reputation · Local records</p>
      <h1>Reviews</h1>
      <p>Keep the feedback, the reply draft and the next step together.</p>
    </div>
  </header>
  <p class="mp-notice">
    <strong>Local only — nothing is requested or posted.</strong> These are staff-entered records, not
    verified provider totals. Patient links are internal and do not verify who wrote a public review.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  <form method="GET" class="mp-panel mp-form">
    <div class="mp-form-grid">
      {#if data.filters.patient}<input
          name="patient"
          type="hidden"
          value={data.filters.patient}
        />{/if}
      <label
        >Review date from (UTC)<input type="date" name="start" required value={info.start} /></label
      >
      <label>Through (UTC)<input type="date" name="end" required value={info.end} /></label>
      <label
        >Search patients or review text<input
          name="search"
          maxlength="100"
          value={data.filters.search || ''}
          placeholder="Patient name or review text"
        /></label
      >
      <label
        >List status<select name="status" value={data.filters.status || 'active'}
          ><option value="active">All non-archived</option><option value="all"
            >All including archived</option
          >{#each info.statuses as [value, name] (value)}<option {value}>{name}</option
            >{/each}</select
        ></label
      >
      <label
        >List source<select name="source" value={data.filters.source || 'all'}
          ><option value="all">All sources</option
          >{#each info.sources as [value, name] (value)}<option {value}>{name}</option
            >{/each}</select
        ></label
      >
      <button class="mp-button">Apply filters</button>
    </div>
    <a href={resolve('/reviews')}>Reset to last 30 UTC days</a>
  </form>
  <p class="summary-scope">
    Summary: accessible non-archived records by review date, {info.start} through {info.end},
    inclusive UTC days{data.filters.patient ? ', for this patient' : ''}. List status, source and
    text filters do not change summary totals. Unrated reviews are excluded from averages.
  </p>
  <section class="review-summary" aria-label="Recorded review summary">
    <article class="review-score">
      <h2>Recorded average</h2>
      <strong class="score">{average(info.summary.average)}</strong>
      <p>
        {info.summary.count} reviews · {info.summary.rated_count} rated · {info.summary
          .unrated_count} unrated
      </p>
      <div class="rating-bars">
        {#each info.summary.histogram as row (row.rating)}<div>
            <span>{row.rating} star</span><meter
              min="0"
              max={Math.max(1, info.summary.rated_count)}
              value={row.count}
              aria-label={`${row.rating}-star reviews`}
            ></meter><span>{row.count}</span>
          </div>{/each}
      </div>
      <p>{info.summary.needs_attention} need attention or are in progress</p>
    </article>
    <div class="source-grid">
      {#each info.summary.sources as source (source.source)}<article class="mp-panel source-score">
          <h2>{source.label}</h2>
          <strong>{average(source.average)}</strong>
          <p>{source.count} reviews · {source.rated_count} rated</p>
        </article>{/each}
    </div>
  </section>
  <div class="mp-columns">
    <section class="mp-panel">
      <div class="mp-panel-heading">
        <h2>Latest recorded reviews</h2>
        <span>Newest review date first</span>
      </div>
      <div class="mp-form">
        {#each info.reviews as review (review.id)}<article class="mp-followup">
            <p class="review-rating">
              {review.rating === null ? 'Rating not recorded' : `${review.rating} / 5 stars`} · {label(
                info.sources,
                review.source
              )}
            </p>
            <h3>
              <a href={resolve(asInternalPath(`/reviews/${review.id}`))}>{review.patient_name}</a>
            </h3>
            <p class="review-body">{review.body || 'Review text not recorded.'}</p>
            <p>{label(info.statuses, review.status)} · {dateTime(review.reviewed_at)}</p>
            <a href={resolve(asInternalPath(`/reviews/${review.id}`))}
              >Review record and local reply</a
            >
          </article>{:else}<p>
            No reviews match these list filters. Missing reviews are not treated as zero-star
            ratings.
          </p>{/each}
      </div>
    </section>
    <div>
      <section class="mp-panel mp-form">
        <h2>Record a review</h2>
        <p>
          Search at least two characters of a patient's name above, or open Local reviews from their
          journey. Record only known facts; leave missing ratings blank.
        </p>
        {#if info.patient_choices.length}<form method="POST" action="?/create" class="mp-form">
            <input
              type="hidden"
              name="request_id"
              value={form?.values?.request_id || data.requestKey}
            /><label
              >Internal patient link<select
                name="patient"
                required
                value={form?.values?.patient || info.patient_choices[0]?.id}
                >{#each info.patient_choices as patient (patient.id)}<option value={patient.id}
                    >{patient.name}</option
                  >{/each}</select
              ></label
            ><label
              >Review source<select name="source" value={form?.values?.source || 'unknown'}
                >{#each info.sources as [value, name] (value)}<option {value}>{name}</option
                  >{/each}</select
              ></label
            ><label
              >Recorded star rating<select name="rating" value={form?.values?.rating || ''}
                ><option value="">Not recorded</option
                >{#each [1, 2, 3, 4, 5] as rating (rating)}<option value={rating}
                    >{rating} / 5</option
                  >{/each}</select
              ></label
            ><label
              >Actual review date and time (UTC)<input
                type="datetime-local"
                name="reviewed_at"
                required
                value={form?.values?.reviewed_at || nowInput()}
              /></label
            ><label
              >Review text<textarea name="body" maxlength="5000" rows="5"
                >{form?.values?.body || ''}</textarea
              ></label
            >
            <p>
              Review facts stay in history. For an entry mistake, archive it with a reason and
              record a replacement.
            </p>
            <button class="mp-button">Save local review record</button>
          </form>{/if}
        {#if info.more_patients}<p>
            Showing 20 patient choices. Refine the search to find others.
          </p>{/if}
      </section>
      <section class="mp-panel mp-form">
        <h2>Review requests</h2>
        <span class="mp-badge">Not implemented</span>
        <p>
          Connected review requests, automatic reminders, private feedback forms and public replies
          are future work. No invitations, response rates or provider totals are inferred from these
          records.
        </p>
      </section>
    </div>
  </div>
  <RecordPages pages={info.pages} />
</div>

<style>
  .summary-scope {
    margin: 20px 0;
    color: #555b65;
    font-size: 13px;
    line-height: 1.5;
  }
  .review-summary {
    display: grid;
    grid-template-columns: minmax(240px, 1fr) minmax(0, 2fr);
    gap: 16px;
    margin-bottom: 24px;
  }
  .review-score {
    background: #17191d;
    color: #fff;
    padding: 24px;
    border-radius: 18px;
  }
  .review-score h2 {
    color: #fff;
  }
  .score {
    display: block;
    font-size: clamp(30px, 4vw, 56px);
    line-height: 1.25;
    margin: 12px 0;
  }
  .rating-bars {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 18px 0;
  }
  .rating-bars div {
    display: grid;
    grid-template-columns: 50px 1fr 25px;
    gap: 12px;
    align-items: center;
    font-size: 12px;
  }
  .rating-bars meter {
    width: 100%;
    height: 14px;
    accent-color: #e472a8;
  }
  .source-grid {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 16px;
  }
  .source-score {
    grid-column: span 2;
    padding: 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 14px;
  }
  .source-score:nth-child(n + 4) {
    grid-column: span 3;
  }
  .rating-bars meter::-webkit-meter-optimum-value {
    background: #e472a8;
  }
  .rating-bars meter::-moz-meter-bar {
    background: #e472a8;
  }
  .source-score strong {
    font-size: 25px;
  }
  .source-score p {
    font-size: 12px;
    color: #616670;
  }
  .review-rating {
    color: #925000;
    font-weight: 600;
  }
  .review-body {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  @media (max-width: 1000px) {
    .review-summary {
      grid-template-columns: 1fr;
    }
  }
  @media (max-width: 600px) {
    .source-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .source-score,
    .source-score:nth-child(n + 4) {
      grid-column: auto;
    }
    .source-score:last-child {
      grid-column: span 2;
    }
  }
</style>
