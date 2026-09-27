<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { dateTime } from '$lib/modern-practice.js';
  let { data, form } = $props();
  let selected = $derived(data.selected);
  let booking = $derived({
    title: '',
    location: '',
    starts_at: '',
    ends_at: '',
    request_id: data.bookingKey,
    ...(form?.action === 'appointments' ? form.values : {})
  });
  let changes = $derived(
    form?.values?.appointment_id && form.values.appointment_id === selected?.id ? form.values : {}
  );
  let action = $derived(
    String(changes?.action || (selected?.can_reopen ? 'reopened' : 'rescheduled'))
  );
  /** @type {Record<string, string>} */
  const labels = {
    scheduled: 'Scheduled',
    booked: 'Booked',
    rescheduled: 'Rescheduled',
    reopened: 'Reopened',
    attended: 'Attended',
    cancelled: 'Cancelled',
    no_show: 'No-show'
  };
  /** @param {string} value */
  const localInput = (value) => (value ? new Date(value).toISOString().slice(0, 16) : '');
  let editDraft = $derived({
    reason: changes?.reason || '',
    starts_at: changes?.starts_at || localInput(selected?.starts_at),
    ends_at: changes?.ends_at || localInput(selected?.ends_at)
  });
  let base = $derived(`/patients/${data.patient.id}/appointments`);
</script>

<svelte:head><title>Appointments · {data.patient.name} | Modern Practice</title></svelte:head>
<div class="mp-page">
  <a href={resolve(asInternalPath(`/patients/${data.patient.id}`))}>← Patient journey</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Patient scheduling · UTC</p>
      <h1>Appointments</h1>
      <p>{data.patient.name}</p>
    </div>
  </header>
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration appointments only
    </p>{/if}
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  <p class="mp-notice">
    Booking adds one event at the time it is recorded. Rescheduling does not add another.
    Cancellation and no-show preserve the historical booking count. Attendance never records
    treatment or revenue.
  </p>
  <div class="mp-columns">
    <div>
      <section class="mp-panel">
        <div class="mp-panel-heading pink">
          <h2>Scheduled times and outcomes</h2>
          <span
            >{data.appointments.count}
            {data.appointments.count === 1 ? 'appointment' : 'appointments'}</span
          >
        </div>
        <div class="mp-form">
          {#each data.appointments.results as appointment (appointment.id)}
            <article class="mp-followup">
              <a
                aria-current={selected?.id === appointment.id ? 'page' : undefined}
                href={resolve(
                  asInternalPath(
                    `${base}?page=${data.appointments.page}&appointment=${appointment.id}`
                  )
                )}><strong>{appointment.title}</strong></a
              >
              <p>{dateTime(appointment.starts_at)} → {dateTime(appointment.ends_at)}</p>
              <p class="mp-muted">
                {labels[appointment.status]} · {appointment.location || 'No location entered'}
              </p>
            </article>
          {:else}<p>No appointments recorded. Schedule the first one below.</p>{/each}
          <nav class="mp-patient-links" aria-label="Appointment pages">
            {#if data.appointments.page > 1}<a
                href={resolve(asInternalPath(`${base}?page=${data.appointments.page - 1}`))}
                >← Previous</a
              >{/if}
            {#if data.appointments.page * data.appointments.page_size < data.appointments.count}<a
                href={resolve(asInternalPath(`${base}?page=${data.appointments.page + 1}`))}
                >Next →</a
              >{/if}
          </nav>
        </div>
      </section>
      <section class="mp-panel">
        <div class="mp-panel-heading"><h2>Schedule an appointment</h2></div>
        <form class="mp-form" method="POST" action="?/book">
          <input type="hidden" name="request_id" value={booking?.request_id || data.bookingKey} />
          <label
            >Appointment title<input
              name="title"
              maxlength="200"
              required
              bind:value={booking.title}
            /></label
          >
          <label
            >Location <span class="mp-muted">(optional)</span><input
              name="location"
              maxlength="200"
              bind:value={booking.location}
            /></label
          >
          <div class="mp-form-grid">
            <label
              >Starts · UTC<input
                name="starts_at"
                type="datetime-local"
                required
                bind:value={booking.starts_at}
              /></label
            >
            <label
              >Ends · UTC<input
                name="ends_at"
                type="datetime-local"
                required
                bind:value={booking.ends_at}
              /></label
            >
          </div>
          <p class="mp-muted">
            Times must be in the future. Overlapping scheduled appointments for this patient are
            rejected. Provider and room availability are not checked. No reminders or invitations
            are sent.
          </p>
          <button class="mp-button">Book appointment</button>
        </form>
      </section>
    </div>
    <div>
      {#if selected}
        <section class="mp-panel">
          <div class="mp-panel-heading">
            <h2>{selected.title}</h2>
            <span class="mp-badge">{labels[selected.status]}</span>
          </div>
          <div class="mp-form">
            <p>{dateTime(selected.starts_at)} → {dateTime(selected.ends_at)}</p>
            <p class="mp-muted">
              {selected.location || 'No location entered'} · Version {selected.revision}
            </p>
          </div>
          {#if selected.status === 'scheduled' || selected.can_reopen}
            <form
              class="mp-form"
              method="POST"
              action={`?/change&appointment=${selected.id}&page=${data.appointments.page}`}
            >
              <input type="hidden" name="appointment_id" value={selected.id} />
              <input type="hidden" name="revision" value={selected.revision} />
              {#if selected.can_reopen}
                <p class="mp-notice">
                  Reopen a cancellation or no-show recorded in error. Choose a future time and
                  explain the correction. The previous outcome stays in history; no extra booking
                  event or revenue is recorded. For a separate visit, book a new appointment
                  instead.
                </p>
                <input type="hidden" name="action" value="reopened" />
              {:else}<label
                  >Change<select name="action" bind:value={action}
                    ><option value="rescheduled">Reschedule</option><option value="cancelled"
                      >Cancel</option
                    ><option value="attended">Record attendance</option><option value="no_show"
                      >Record no-show</option
                    ></select
                  ></label
                >
              {/if}
              {#if action === 'rescheduled' || selected.can_reopen}<div class="mp-form-grid">
                  <label
                    >New start · UTC<input
                      name="starts_at"
                      type="datetime-local"
                      required
                      bind:value={editDraft.starts_at}
                    /></label
                  >
                  <label
                    >New end · UTC<input
                      name="ends_at"
                      type="datetime-local"
                      required
                      bind:value={editDraft.ends_at}
                    /></label
                  >
                </div>{/if}
              <label
                >Reason<textarea
                  name="reason"
                  required
                  maxlength="1000"
                  rows="3"
                  bind:value={editDraft.reason}></textarea></label
              >
              <p class="mp-muted">
                Attendance can be recorded after the start; no-show after the end. Closing an
                appointment preserves its history. Only practice administrators can reopen
                cancellations or no-shows.
              </p>
              <button class="mp-button"
                >{selected.can_reopen ? 'Reopen appointment' : 'Save appointment change'}</button
              >
            </form>
          {:else}<p class="mp-form mp-muted">
              This appointment is closed. {selected.status === 'attended'
                ? 'Corrections to recorded attendance are not supported yet.'
                : 'Only a practice administrator can reopen a cancellation or no-show.'}
              Book a new appointment for a separate visit.
            </p>{/if}
        </section>
        <section class="mp-panel">
          <div class="mp-panel-heading">
            <h2>Change history</h2>
            <span class="mp-muted">Oldest first · UTC</span>
          </div>
          <ol class="mp-timeline">
            {#each selected.history as entry (entry.id)}<li>
                <div class="mp-timeline-dot"></div>
                <div>
                  <time>{dateTime(entry.at)}</time>
                  <h3>{labels[entry.action]}</h3>
                  <p>{entry.reason}</p>
                  {#if entry.action === 'reopened'}<p>
                      {labels[entry.before.status]} → {labels[entry.after.status]}
                    </p>{/if}
                  <p class="mp-muted">Recorded by {entry.actor}</p>
                  {#if entry.action === 'rescheduled' || entry.action === 'reopened'}<p>
                      From {dateTime(entry.before.starts_at)} → {dateTime(entry.before.ends_at)}
                    </p>{/if}
                  <p>
                    Appointment: {dateTime(entry.after.starts_at)} → {dateTime(entry.after.ends_at)}
                  </p>
                </div>
              </li>{/each}
          </ol>
        </section>
      {/if}
    </div>
  </div>
</div>
