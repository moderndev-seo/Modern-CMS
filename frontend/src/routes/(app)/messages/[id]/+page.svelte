<script>
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { dateTime, nowInput } from '$lib/modern-practice.js';
  import DraftGuard from '$lib/components/modern-practice/DraftGuard.svelte';
  import RecordPages from '$lib/components/modern-practice/RecordPages.svelte';
  let { data, form } = $props();
  let info = $derived(data.detail);
  let thread = $derived(info.conversation);
  let draft = $derived(form?.values?.action === 'draft' ? form.values.draft : thread.draft);
  /** @type {HTMLFormElement | undefined} */
  let draftForm = $state();
  let templateId = $state('');
  const kinds = {
    note: 'Internal note',
    received: 'Manually logged incoming',
    outbound_log: 'Manually logged outgoing'
  };
</script>

<svelte:head><title>{thread.subject} · Messages | Modern Practice</title></svelte:head>
<div class="mp-page">
  {#if data.org?.name?.startsWith('TEST -')}<p class="mp-demo">
      {data.org.name} · Fictional demonstration records only
    </p>{/if}
  <a href={resolve('/messages')}>← Messages</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Local conversation · {thread.status}</p>
      <h1>{thread.subject}</h1>
      <a href={resolve(asInternalPath(`/patients/${thread.patient}`))}
        >{thread.patient_name} · Patient journey</a
      >
    </div>
  </header>
  <p class="mp-notice">
    <strong>Local only — nothing is sent.</strong> Manual entries record what staff report; they do not
    prove delivery or a patient response. Saved drafts are shared with staff who can access this patient.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  {#if page.url.searchParams.has('saved')}<p role="status" class="mp-notice">
      {page.url.searchParams.get('saved') === 'followup'
        ? 'Follow-up task created. Review it in Messages or Tasks.'
        : 'Saved locally.'}
    </p>{/if}
  <div class="mp-columns">
    <div>
      <section class="mp-panel mp-form">
        <h2>Conversation history</h2>
        <p>
          Newest event first · Dates in UTC. Entries cannot be edited or deleted; add a clarifying
          note to correct a record.
        </p>
        {#each info.entries as entry (entry.id)}<article class="mp-followup">
            <h3>{kinds[entry.kind]}</h3>
            <p class="message-body">{entry.body}</p>
            <small
              >{dateTime(entry.occurred_at)} · Recorded by {entry.actor} on {dateTime(
                entry.recorded_at
              )}</small
            >
          </article>{:else}<p>No entries recorded yet.</p>{/each}
      </section>
      <section class="mp-panel mp-form">
        <h2>Add a local entry</h2>
        {#if thread.status === 'resolved'}<p>
            Reopen this conversation before adding entries or changing its draft.
          </p>{:else}
          <form method="POST" action="?/entry" class="mp-form">
            <input
              type="hidden"
              name="request_id"
              value={form?.action === 'entries' ? form.values.request_id : data.entryKey}
            />
            <label
              >Entry type<select name="kind"
                ><option value="note">Internal note</option><option value="received"
                  >Manually logged incoming</option
                ><option value="outbound_log">Manually logged outgoing</option></select
              ></label
            >
            <label
              >Actual event time (UTC)<input
                type="datetime-local"
                name="occurred_at"
                required
                value={form?.action === 'entries' ? form.values.occurred_at : nowInput()}
              /></label
            >
            <label
              >What happened?<textarea name="body" required maxlength="5000" rows="5"
                >{form?.action === 'entries' ? form.values.body : ''}</textarea
              ></label
            ><button class="mp-button">Record local entry</button>
          </form>
        {/if}
      </section>
      <section class="mp-panel mp-form">
        <h2>Change history</h2>
        <p>
          Ownership, status and draft revisions, newest first. Previous draft text remains in this
          history.
        </p>
        {#each info.history as change (change.id)}<details>
            <summary
              >Revision {change.revision} · {change.action === 'draft'
                ? 'Local draft'
                : 'Ownership / status'} · {dateTime(change.at)}</summary
            >
            <p>Recorded by {change.actor}</p>
            {#if change.action === 'draft'}<p>Before:</p>
              <pre class="message-body">{change.before.draft || '(empty)'}</pre>
              <p>After:</p>
              <pre class="message-body">{change.after.draft || '(empty)'}</pre>{:else}<p>
                Status: {change.before.status} → {change.after.status}
              </p>
              <p>
                Owner: {change.before_owner} → {change.after_owner}
              </p>{/if}
          </details>{:else}<p>No changes yet.</p>{/each}
      </section>
    </div>
    <div>
      <section class="mp-panel mp-form">
        <h2>Ownership and next step</h2>
        <p>Current owner: {thread.owner_name}. Ownership never grants access to a patient.</p>
        <form method="POST" action="?/state" class="mp-form">
          <input type="hidden" name="request_id" value={data.stateKey} /><input
            type="hidden"
            name="revision"
            value={thread.revision}
          /><label
            >Owner<select name="owner" value={thread.owner || ''}
              ><option value="">Unassigned</option>{#each info.owners as owner (owner.id)}<option
                  value={owner.id}>{owner.name}</option
                >{/each}</select
            ></label
          ><label
            >Status<select name="status" value={thread.status}
              ><option value="open">Open — action needed</option><option value="waiting"
                >Waiting — follow up later</option
              ><option value="resolved">Resolved</option></select
            ></label
          ><button class="mp-button">Save ownership / status</button>
        </form>
      </section>
      <section class="mp-panel mp-form">
        <h2>Local draft</h2>
        <p>
          Saving or applying a template never sends a message. Review and personalize its text
          before using it outside this workspace.
        </p>
        {#if thread.status !== 'resolved'}<label
            >Starting template<select bind:value={templateId}
              ><option value="">Choose a template</option
              >{#each info.templates as template (template.id)}<option value={template.id}
                  >{template.title}</option
                >{/each}</select
            ></label
          ><button
            type="button"
            disabled={!templateId}
            onclick={() => {
              const chosen = info.templates.find((item) => item.id === templateId);
              if (chosen) draft = draft ? `${draft}\n\n${chosen.body}` : chosen.body;
            }}>Append template to draft</button
          >{/if}
        <DraftGuard dirty={draft !== thread.draft} {draftForm} />
        <form bind:this={draftForm} method="POST" action="?/draft" class="mp-form">
          <input
            type="hidden"
            name="request_id"
            value={form?.values?.action === 'draft' ? form.values.request_id : data.draftKey}
          /><input type="hidden" name="revision" value={thread.revision} /><label
            >Draft text<textarea
              name="draft"
              bind:value={draft}
              maxlength="5000"
              rows="7"
              readonly={thread.status === 'resolved'}></textarea></label
          >{#if thread.status !== 'resolved'}<button class="mp-button">Save local draft</button>
            <p>Save an empty draft to clear it. Earlier versions stay in change history.</p>{/if}
        </form>
      </section>
      <section class="mp-panel mp-form">
        <h2>Create a patient follow-up</h2>
        <p>
          Creates an existing CRM task assigned to you and linked to this patient. No reminder is
          sent.
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
  .message-body {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font: inherit;
  }
</style>
