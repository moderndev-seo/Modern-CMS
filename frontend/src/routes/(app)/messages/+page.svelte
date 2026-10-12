<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { dateTime } from '$lib/modern-practice.js';
  import RecordPages from '$lib/components/modern-practice/RecordPages.svelte';
  let { data, form } = $props();
  let inbox = $derived(data.inbox);
</script>

<svelte:head><title>Messages | Modern Practice</title></svelte:head>
<div class="mp-page">
  {#if data.org?.name?.startsWith('TEST -')}<p class="mp-demo">
      {data.org.name} · Fictional demonstration records only
    </p>{/if}
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Modern Practice · Team workspace</p>
      <h1>Messages</h1>
      <p>Keep conversations and the next step together.</p>
    </div>
    <a href={resolve('/messages/templates')}>Local templates</a>
  </header>
  <p class="mp-notice">
    <strong>Local only — nothing is sent.</strong> Staff manually record conversations here. There is
    no connected inbox, delivery confirmation or automatic reminder.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  <section class="mp-panel mp-form" aria-label="Conversation filters">
    <p>
      <strong>{inbox.counts.open}</strong> open · <strong>{inbox.counts.waiting}</strong> waiting ·
      <strong>{inbox.counts.resolved}</strong>
      resolved. Counts include your accessible conversations{data.filters.patient
        ? ' for this patient'
        : ''}, across all dates.
    </p>
    <form method="GET" class="mp-form-grid">
      {#if data.filters.patient}<input
          type="hidden"
          name="patient"
          value={data.filters.patient}
        />{/if}
      <label
        >Search patients or subjects<input
          name="search"
          maxlength="100"
          value={data.filters.search || ''}
          placeholder="Patient name or subject"
        /></label
      >
      <label
        >Status<select name="status" value={data.filters.status || 'active'}
          ><option value="active">Open and waiting</option><option value="open">Open</option><option
            value="waiting">Waiting</option
          ><option value="resolved">Resolved</option><option value="all">All statuses</option
          ></select
        ></label
      >
      <label
        >Owner<select name="owner" value={data.filters.owner || 'all'}
          ><option value="all">All owners</option><option value="mine">Assigned to me</option
          ><option value="unassigned">Unassigned</option></select
        ></label
      >
      <label
        >Follow-ups<select name="tasks" value={data.filters.tasks || 'due'}
          ><option value="due">Due today or overdue (UTC)</option><option value="all"
            >All unfinished follow-ups</option
          ></select
        ></label
      >
      <button class="mp-button">Apply filters</button><a href={resolve('/messages')}
        >Clear filters</a
      >
    </form>
  </section>
  <div class="mp-columns">
    <section class="mp-panel mp-form">
      <h2>Conversations</h2>
      <p>Most recently updated first.</p>
      {#each inbox.conversations as row (row.id)}<article class="mp-followup">
          <h3><a href={resolve(asInternalPath(`/messages/${row.id}`))}>{row.subject}</a></h3>
          <p>{row.patient_name} · {row.status} · {row.owner_name}</p>
          <small>Updated {dateTime(row.updated_at)}</small>
        </article>{:else}<p>
          No conversations match these filters. Search for a patient to start one.
        </p>{/each}
    </section>
    <div>
      <section class="mp-panel mp-form">
        <h2>Start a conversation</h2>
        <p>
          Search for at least two characters of a patient's name above, or open Messages from their
          patient record.
        </p>
        {#if inbox.patient_choices.length}<form method="POST" action="?/create" class="mp-form">
            <input
              type="hidden"
              name="request_id"
              value={form?.values?.request_id || data.requestKey}
            /><label
              >Patient<select name="patient" required
                >{#each inbox.patient_choices as patient (patient.id)}<option value={patient.id}
                    >{patient.name}</option
                  >{/each}</select
              ></label
            ><label
              >Subject<input
                name="subject"
                required
                maxlength="200"
                value={form?.values?.subject || ''}
              /></label
            ><button class="mp-button">Create local conversation</button>
          </form>{/if}
        {#if inbox.more_patients}<p>Showing 20 patients. Refine your search to find others.</p>{/if}
      </section>
      <section class="mp-panel mp-form">
        <h2>Patient follow-ups</h2>
        <p>
          {inbox.followup_due_count} unfinished tasks due today or overdue (UTC), across your accessible
          patients. Task permissions still apply.
        </p>
        {#each inbox.followups as task (task.id)}<article class="mp-followup">
            <a href={resolve(asInternalPath(`/tasks/${task.id}`))}>{task.title}</a>
            <p>{task.status} · Due {task.due_date || 'date not set'}</p>
          </article>{:else}<p>No follow-ups match this filter.</p>{/each}
      </section>
    </div>
  </div>
  <RecordPages pages={inbox.pages} />
</div>
