<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import {
    sources,
    sourceLabel,
    eventKinds,
    usd,
    dateTime,
    nowInput,
    refundablePayments
  } from '$lib/modern-practice.js';
  let { data, form } = $props();
  let eventKind = $state('booked');
  let receiptKind = $state('payment');
  let eventValues = $derived(form?.action === 'events' ? form.values : {});
  let followupValues = $derived(form?.action === 'tasks' ? form.values : {});
  let receiptValues = $derived(form?.action === 'receipts' ? form.values : {});
  $effect(() => {
    if (eventValues?.kind) eventKind = String(eventValues.kind);
    if (receiptValues?.kind) receiptKind = String(receiptValues.kind);
  });
  let patient = $derived(data.patient);
  let timeline = $derived(
    [
      ...(patient.original_at
        ? [
            {
              id: 'original',
              occurred_at: patient.original_at,
              title: 'Original marketing touch',
              description: `${sourceLabel(patient.original_source)} · ${patient.original_campaign || 'No campaign recorded'}`,
              amount: null
            }
          ]
        : []),
      {
        id: 'lead',
        occurred_at: patient.lead_at,
        title: 'Known lead',
        description: 'Patient journey opened',
        amount: null
      },
      ...patient.events.map((event) => ({
        ...event,
        title: eventKinds.find(([key]) => key === event.kind)?.[1],
        description:
          event.kind === 'touch'
            ? `${sourceLabel(event.source)} · ${event.campaign || 'No campaign recorded'}${event.landing_page ? ' · ' + event.landing_page : ''}${event.notes ? ' · ' + event.notes : ''}`
            : event.notes,
        amount: null
      })),
      ...patient.receipts.map((receipt) => ({
        ...receipt,
        title: receipt.kind === 'payment' ? 'Payment received' : 'Refund issued',
        description: `${receipt.reference}${receipt.notes ? ' · ' + receipt.notes : ''}`,
        amount: (receipt.kind === 'refund' ? '-' : '') + usd(receipt.amount)
      }))
    ].sort((a, b) => new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime())
  );
  let completed = $derived(new Set(patient.events.map((event) => event.kind)));
  let payments = $derived(refundablePayments(patient.receipts));
  let refundable = $derived(payments.some((payment) => payment.remaining > 0));
</script>

<svelte:head><title>{patient.name} | Modern Practice</title></svelte:head>
<div class="mp-page">
  <div class="mp-patient-links">
    <a href={resolve('/patients')}>← Patients</a>
    {#if patient.can_create_followup}<a
        class="mp-button secondary"
        href={resolve(asInternalPath(`/patients/${patient.id}/appointments`))}>Appointments →</a
      >{/if}
  </div>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Patient journey</p>
      <h1>{patient.name}</h1>
      <p class="mp-muted">
        {patient.contact_email || 'No email recorded'} ·
        <a href={resolve(asInternalPath(`/contacts/${patient.contact}`))}>CRM contact</a>
      </p>
    </div>
    <div class="mp-collected">
      <span>Net collected · USD</span><strong>{usd(patient.net_revenue)}</strong>
    </div>
  </header>
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration records only
    </p>{/if}
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  {#if form?.success}<p class="mp-success" role="status">
      Saved. This patient view is up to date.
    </p>{/if}
  <ol class="mp-stages">
    {#each [['lead', 'Known lead'], ['booked', 'Booked'], ['attended', 'Attended'], ['consultation', 'Consultation'], ['treated', 'Treated'], ['paid', 'Payment received']] as [key, label] (key)}<li
        class:complete={key === 'lead' ||
          (key === 'paid' ? payments.length > 0 : completed.has(key))}
      >
        <span
          >{key === 'lead' || (key === 'paid' ? payments.length > 0 : completed.has(key))
            ? '✓'
            : '○'}</span
        >{label}
      </li>{/each}
  </ol>
  <div class="mp-columns">
    <div>
      <section class="mp-panel">
        <div class="mp-panel-heading pink">
          <h2>Original attribution</h2>
          <span class="mp-badge">Preserved</span>
        </div>
        <dl class="mp-facts">
          <div>
            <dt>Source</dt>
            <dd>{sourceLabel(patient.original_source)}</dd>
          </div>
          <div>
            <dt>Campaign</dt>
            <dd>{patient.original_campaign || 'Not recorded'}</dd>
          </div>
          <div>
            <dt>Keyword</dt>
            <dd>{patient.original_keyword || 'Not recorded'}</dd>
          </div>
          <div>
            <dt>First touch</dt>
            <dd>{dateTime(patient.original_at)}</dd>
          </div>
          <div class="mp-wide">
            <dt>Landing page</dt>
            <dd>{patient.original_landing_page || 'Not recorded'}</dd>
          </div>
        </dl>
      </section>
      <section class="mp-panel">
        <div class="mp-panel-heading">
          <h2>Activity</h2>
          <span class="mp-muted">Oldest first · UTC</span>
        </div>
        <ol class="mp-timeline">
          {#each timeline as item (item.id)}<li>
              <div class="mp-timeline-dot"></div>
              <div>
                <time>{dateTime(item.occurred_at)}</time>
                <h3>
                  {item.title}
                  {#if item.amount}<span class="mp-receipt-amount">{item.amount}</span>{/if}
                </h3>
                <p>{item.description || 'No additional notes'}</p>
              </div>
            </li>{/each}
        </ol>
      </section>
    </div>
    <div>
      <section class="mp-panel">
        <div class="mp-panel-heading">
          <h2>Follow-up tasks</h2>
          <a href={resolve('/tasks')}>All tasks →</a>
        </div>
        <div class="mp-form">
          <p class="mp-muted">
            Tasks you can access for this contact. Task completion does not record an appointment,
            treatment, or payment.
          </p>
          {#each patient.followups as task (task.id)}
            <article class="mp-followup">
              <a href={resolve(asInternalPath(`/tasks/${task.id}`))}
                ><strong>{task.title}</strong></a
              >
              <p class="mp-muted">
                {task.due_date ? `Due ${task.due_date}` : 'No due date'} · {task.priority} priority ·
                {task.status}
              </p>
              {#if task.description}<p>{task.description}</p>{/if}
              <form method="POST" action="?/taskStatus">
                <input type="hidden" name="task_id" value={task.id} />
                <label
                  >Status for {task.title}<select name="status" value={task.status}>
                    <option>New</option><option>In Progress</option><option>Completed</option>
                  </select></label
                >
                <button class="mp-button secondary">Save status</button>
              </form>
            </article>
          {:else}<p>No follow-up tasks visible to you for this contact.</p>{/each}
          {#if patient.followup_count > 50}<p class="mp-notice">
              Showing the newest 50 of {patient.followup_count} visible tasks. Open All tasks for more.
            </p>{/if}
        </div>
        {#if patient.can_create_followup}
          <form class="mp-form" method="POST" action="?/followup">
            <h3>Add a follow-up</h3>
            <p class="mp-muted">
              Assigned to you. No email or message is sent. Manage assignments and other edits in
              Tasks.
            </p>
            <label
              >Task title<input
                name="title"
                maxlength="200"
                required
                value={followupValues?.title || ''}
              /></label
            >
            <div class="mp-form-grid">
              <label
                >Due date<input
                  name="due_date"
                  type="date"
                  required
                  value={followupValues?.due_date || ''}
                /></label
              >
              <label
                >Priority<select name="priority" value={followupValues?.priority || 'Medium'}
                  ><option>Low</option><option>Medium</option><option>High</option></select
                ></label
              >
            </div>
            <label
              >Notes<textarea
                name="description"
                maxlength="2000"
                rows="2"
                value={followupValues?.description || ''}></textarea></label
            >
            <button class="mp-button">Create follow-up</button>
          </form>
        {:else}<p class="mp-form mp-muted">
            Contact access is required to create a follow-up. Existing task permissions still apply.
          </p>{/if}
      </section>
      <section class="mp-panel">
        <div class="mp-panel-heading"><h2>Record a milestone</h2></div>
        <form class="mp-form" method="POST" action="?/event">
          <label
            >Event<select name="kind" bind:value={eventKind}
              >{#each eventKinds as [key, label] (key)}<option value={key}>{label}</option
                >{/each}</select
            ></label
          ><label
            >Occurred at · UTC<input
              name="occurred_at"
              type="datetime-local"
              required
              value={eventValues?.occurred_at || nowInput()}
            /></label
          >{#if eventKind === 'touch'}<label
              >Source<select name="source" value={eventValues?.source || 'unknown'}
                ><option value="unknown">Unknown</option
                >{#each sources.filter(([key]) => key !== 'unknown') as [key, label] (key)}<option
                    value={key}>{label}</option
                  >{/each}</select
              ></label
            ><label
              >Campaign<input
                name="campaign"
                maxlength="255"
                value={eventValues?.campaign || ''}
              /></label
            ><label
              >Landing page<input
                name="landing_page"
                type="url"
                maxlength="1000"
                value={eventValues?.landing_page || ''}
              /></label
            >
            <p class="mp-muted">
              This is a subsequent touch. Original attribution stays unchanged.
            </p>{/if}<label
            >Notes<textarea name="notes" maxlength="2000" rows="2" value={eventValues?.notes || ''}
            ></textarea></label
          ><button class="mp-button">Record event</button>
        </form>
      </section>
      <section class="mp-panel">
        <div class="mp-panel-heading">
          <h2>Collected revenue</h2>
          <span class="mp-badge">USD</span>
        </div>
        {#if data.role === 'ADMIN'}<form class="mp-form" method="POST" action="?/receipt">
            <p class="mp-muted">
              Record money actually received or refunded. This does not create or settle an invoice.
              Entries cannot be edited or deleted.
            </p>
            <label
              >Entry type<select name="kind" bind:value={receiptKind}
                ><option value="payment">Payment received</option><option value="refund"
                  >Refund issued</option
                ></select
              ></label
            >{#if receiptKind === 'refund'}<label
                >Original payment<select
                  name="payment"
                  required
                  value={receiptValues?.payment || ''}
                  ><option value="">Choose payment</option
                  >{#each payments as payment (payment.id)}<option
                      value={payment.id}
                      disabled={payment.remaining === 0}
                      >{payment.reference} · {usd(payment.remaining)} refundable</option
                    >{/each}</select
                ></label
              >
              <p class="mp-muted">
                {refundable
                  ? 'Balances reflect recorded refunds. The server checks the remaining amount before saving.'
                  : 'No refundable balance remains. Record a payment before issuing a refund.'}
              </p>
            {/if}
            <div class="mp-form-grid">
              <label
                >Amount · USD<input
                  name="amount"
                  value={receiptValues?.amount || ''}
                  type="number"
                  min="0.01"
                  step="0.01"
                  max="9999999999.99"
                  required
                /></label
              ><label
                >Unique receipt reference<input
                  name="reference"
                  value={receiptValues?.reference || ''}
                  maxlength="100"
                  required
                /></label
              >
            </div>
            <label
              >Received / refunded at · UTC<input
                name="occurred_at"
                type="datetime-local"
                required
                value={receiptValues?.occurred_at || nowInput()}
              /></label
            ><label
              >Notes<textarea
                name="notes"
                rows="2"
                maxlength="2000"
                value={receiptValues?.notes || ''}></textarea></label
            ><button class="mp-button" disabled={receiptKind === 'refund' && !refundable}
              >Record {receiptKind === 'payment' ? 'payment' : 'refund'}</button
            >
          </form>{:else}<p class="mp-form mp-muted">
            A practice administrator can record payments and refunds.
          </p>{/if}
      </section>
    </div>
  </div>
</div>
