<script>
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { dateTime } from '$lib/modern-practice.js';
  import RecordPages from '$lib/components/modern-practice/RecordPages.svelte';
  let { data, form } = $props();
  let info = $derived(data.detail);
  let review = $derived(info.review);
  const label = (options, value) => options.find(([key]) => key === value)?.[1] || value;
</script>

<svelte:head><title>Local review · {review.patient_name} | Modern Practice</title></svelte:head>
<div class="mp-page">
  {#if data.org?.name?.startsWith('TEST -')}<p class="mp-demo">
      {data.org.name} · Fictional demonstration records only
    </p>{/if}
  <a href={resolve('/reviews')}>← Reviews</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Your reputation · Local record</p>
      <h1>Review follow-up</h1>
      <a href={resolve(asInternalPath(`/patients/${review.patient}`))}
        >{review.patient_name} · Patient journey</a
      >
    </div>
  </header>
  <p class="mp-notice">
    <strong>Local only — nothing is posted.</strong> Drafts and statuses are saved for your team. Nothing
    is published to a review site.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">
      {form.error}
    </p>{/if}{#if page.url.searchParams.has('saved')}<p class="mp-notice" role="status">
      {page.url.searchParams.get('saved') === 'followup'
        ? 'Patient follow-up task created. Review it in Tasks or Messages.'
        : 'Saved locally.'}
    </p>{/if}
  <div class="mp-columns">
    <div>
      <section class="mp-panel mp-form">
        <h2>Recorded review</h2>
        <p>
          <strong
            >{review.rating === null ? 'Rating not recorded' : `${review.rating} / 5 stars`}</strong
          >
          · {label(info.sources, review.source)}
        </p>
        <p class="review-body">{review.body || 'Review text not recorded.'}</p>
        <p>Review date: {dateTime(review.reviewed_at)} · Recorded {dateTime(review.recorded_at)}</p>
        <p>Current status: <strong>{label(info.statuses, review.status)}</strong></p>
        <p>
          Patient identity is an internal staff link, not verified review authorship. Review facts
          cannot be overwritten; archive mistaken or duplicate entries with a reason and create a
          replacement if needed.
        </p>
      </section>
      <section class="mp-panel mp-form">
        <h2>Local reply draft</h2>
        <p>
          Visible to staff with patient access. Save an empty draft to clear it; previous text stays
          in history.
        </p>
        <form method="POST" action="?/draft" class="mp-form">
          <input
            type="hidden"
            name="request_id"
            value={form?.values?.action === 'draft' ? form.values.request_id : data.draftKey}
          /><input type="hidden" name="revision" value={review.revision} /><label
            >Reply draft<textarea
              name="draft"
              rows="7"
              maxlength="5000"
              readonly={review.status === 'archived'}
              >{form?.values && 'draft' in form.values ? form.values.draft : review.draft}</textarea
            ></label
          >{#if review.status === 'archived'}<p>
              Restore this record to edit its draft.
            </p>{:else}<button class="mp-button">Save local draft</button>{/if}
        </form>
      </section>
      <section class="mp-panel mp-form">
        <h2>Change history</h2>
        <p>Newest revision first. Status reasons and previous drafts remain available.</p>
        {#each info.history as change (change.id)}<details>
            <summary
              >Revision {change.revision} · {change.action === 'draft'
                ? 'Local draft'
                : 'Local status'} · {dateTime(change.at)}</summary
            >
            <p>Recorded by {change.actor}</p>
            {#if change.action === 'draft'}<p>Before:</p>
              <p class="review-body">{change.before.draft || '(empty)'}</p>
              <p>After:</p>
              <p class="review-body">{change.after.draft || '(empty)'}</p>{:else}<p>
                {label(info.statuses, change.before.status)} → {label(
                  info.statuses,
                  change.after.status
                )}
              </p>
              <p>{change.reason}</p>{/if}
          </details>{:else}<p>No changes yet.</p>{/each}
      </section>
    </div>
    <div>
      <section class="mp-panel mp-form">
        <h2>Update local status</h2>
        <p>
          Handled locally does not mean a response was published. Archiving removes this record from
          all summary averages/counts in its original review period; restoring includes it again.
          History is retained.
        </p>
        <form method="POST" action="?/status" class="mp-form">
          <input
            name="request_id"
            type="hidden"
            value={form?.values?.action === 'status' ? form.values.request_id : data.statusKey}
          /><input name="revision" type="hidden" value={review.revision} /><label
            >Status<select
              name="status"
              value={form?.values && 'status' in form.values ? form.values.status : review.status}
              >{#each info.statuses as [value, name] (value)}<option {value}>{name}</option
                >{/each}</select
            ></label
          ><label
            >Reason<textarea name="reason" required maxlength="1000" rows="3"
              >{form?.values && 'reason' in form.values ? form.values.reason : ''}</textarea
            ></label
          ><button class="mp-button">Save status with reason</button>
        </form>
      </section>
      <section class="mp-panel mp-form">
        <h2>Patient follow-up</h2>
        <p>
          Create an existing CRM task assigned to you and linked to this patient. No reminder is
          sent; review status does not complete the task.
        </p>
        <form method="POST" action="?/followup" class="mp-form">
          <label>Next step<input name="title" required maxlength="200" /></label><label
            >Due date (UTC)<input name="due_date" type="date" required /></label
          ><label>Details<textarea name="description" rows="3"></textarea></label><button
            class="mp-button">Create follow-up task</button
          >
        </form>
      </section>
    </div>
  </div>
  <RecordPages pages={info.pages} />
</div>

<style>
  .review-body {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
</style>
