<script>
  import { enhance, applyAction } from '$app/forms';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { resolve } from '$app/paths';
  import { sources, nowInput } from '$lib/modern-practice.js';
  let { form } = $props();
  let linkExisting = $derived(Boolean(form?.values?.contact));
  let selectedId = $derived(String(form?.values?.contact || ''));
  let selectedLabel = $derived(String(form?.values?.contact_label || 'Selected contact'));
  let lookup = $derived(form?.lookup || null);
  let searching = $state(false);
  let searchQuery = $derived(String(form?.lookup?.query || ''));
  let draft = $derived({
    first_name: '',
    last_name: '',
    email: '',
    lead_at: nowInput(),
    original_source: 'unknown',
    original_at: '',
    original_campaign: '',
    original_keyword: '',
    original_landing_page: '',
    ...form?.values
  });
  /** @type {import('@sveltejs/kit').SubmitFunction} */
  function searchContacts() {
    searching = true;
    return async ({ result }) => {
      searching = false;
      if (result.type === 'success' || result.type === 'failure') {
        lookup = result.data?.lookup || { error: 'Could not search contacts. Try again.' };
      } else {
        await applyAction(result);
      }
    };
  }
</script>

<svelte:head><title>Add patient | Modern Practice</title></svelte:head>
<div class="mp-page mp-narrow">
  <a href={resolve('/patients')}>← Patients</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Start the journey</p>
      <h1>Add patient</h1>
      <p class="mp-muted">Record only what is known. Missing attribution stays Unknown.</p>
    </div>
  </header>
  {#if form?.error}<p class="mp-error" role="alert">{form.error}</p>{/if}
  <section class="mp-panel mp-form" aria-labelledby="contact-search-title">
    <h2 id="contact-search-title">Find an existing patient or contact</h2>
    <p class="mp-muted">
      Search this practice before creating a new identity. Matching names alone do not establish
      that two people are the same.
    </p>
    <form method="POST" action="?/search" use:enhance={searchContacts}>
      <label
        >Name or email<input
          name="search"
          required
          minlength="2"
          maxlength="100"
          bind:value={searchQuery}
        /></label
      >
      <button class="mp-button secondary" disabled={searching}
        >{searching ? 'Searching…' : 'Search contacts'}</button
      >
    </form>
    {#if lookup?.error}<p class="mp-error" role="alert">{lookup.error}</p>{/if}
    {#if lookup && !lookup.error}
      <div aria-live="polite">
        <p class="mp-muted">
          {lookup.results.length}
          {lookup.results.length === 1 ? 'match' : 'matches'}{lookup.has_more
            ? ' shown · refine your search for more'
            : ''}
        </p>
        {#each lookup.results as contact (contact.id)}
          <div class="mp-contact-result">
            <div>
              <strong>{contact.name}</strong>
              <p class="mp-muted">
                {contact.email || 'No email recorded'}{contact.is_active
                  ? ''
                  : ' · Inactive contact'}
              </p>
            </div>
            {#if contact.patient_id}
              <a
                class="mp-button secondary"
                href={resolve(asInternalPath(`/patients/${contact.patient_id}`))}>Open journey</a
              >
            {:else}
              <button
                type="button"
                class="mp-button secondary"
                onclick={() => {
                  selectedId = contact.id;
                  selectedLabel = `${contact.name} · ${contact.email || 'No email recorded'}`;
                  linkExisting = true;
                }}>Select contact</button
              >
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </section>
  <form method="POST" action="?/create" class="mp-panel mp-form">
    <h2>Patient identity</h2>
    <label class="mp-check"
      ><input type="checkbox" bind:checked={linkExisting} /> Link an existing CRM contact</label
    >
    {#if linkExisting}
      <input type="hidden" name="contact" value={selectedId} />
      <input type="hidden" name="contact_label" value={selectedLabel} />
      <p role="status">
        {selectedId ? selectedLabel : 'Search above and select a contact to continue.'}
      </p>
      <p class="mp-muted">
        Only contacts in this practice can be linked. Identity remains managed in Contacts.
      </p>{:else}<div class="mp-form-grid">
        <label
          >First name<input
            name="first_name"
            required
            maxlength="255"
            bind:value={draft.first_name}
          /></label
        ><label
          >Last name<input name="last_name" maxlength="255" bind:value={draft.last_name} /></label
        ><label class="mp-wide"
          >Email <span class="mp-muted">(optional)</span><input
            name="email"
            type="email"
            bind:value={draft.email}
          /></label
        >
      </div>{/if}
    <label
      >Known lead timestamp · UTC<input
        type="datetime-local"
        name="lead_at"
        required
        bind:value={draft.lead_at}
      /></label
    >
    <div class="mp-divider"></div>
    <h2>Original marketing source</h2>
    <p class="mp-muted">
      Saved once. Future marketing activity is added separately and never replaces these fields.
    </p>
    <div class="mp-form-grid">
      <label
        >Source<select name="original_source" bind:value={draft.original_source}
          >{#each sources as [key, label] (key)}<option value={key}>{label}</option>{/each}</select
        ></label
      ><label
        >First-touch timestamp · UTC<input
          type="datetime-local"
          name="original_at"
          bind:value={draft.original_at}
        /></label
      ><label
        >Campaign<input
          name="original_campaign"
          maxlength="255"
          bind:value={draft.original_campaign}
        /></label
      ><label
        >Keyword<input
          name="original_keyword"
          maxlength="255"
          bind:value={draft.original_keyword}
        /></label
      ><label class="mp-wide"
        >Landing page<input
          name="original_landing_page"
          type="url"
          maxlength="1000"
          placeholder="https://…"
          bind:value={draft.original_landing_page}
        /></label
      >
    </div>
    <button class="mp-button" disabled={linkExisting && !selectedId}>Create patient journey</button>
  </form>
</div>
