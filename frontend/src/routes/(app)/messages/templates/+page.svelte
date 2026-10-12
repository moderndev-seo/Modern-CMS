<script>
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import RecordPages from '$lib/components/modern-practice/RecordPages.svelte';
  let { data, form } = $props();
</script>

<svelte:head><title>Local message templates | Modern Practice</title></svelte:head>
<div class="mp-page">
  {#if data.org?.name?.startsWith('TEST -')}<p class="mp-demo">
      {data.org.name} · Fictional demonstration records only
    </p>{/if}
  <a href={resolve('/messages')}>← Messages</a>
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">Modern Practice · Local only</p>
      <h1>Message templates</h1>
      <p>Reusable text for your practice's saved drafts.</p>
    </div>
  </header>
  <p class="mp-notice">
    Nothing is sent. Templates are plain text: there is no automatic personalization. Administrators
    can add or archive templates. To revise wording, create a new template and archive the old one.
  </p>
  {#if form?.error}<p class="mp-error" role="alert">
      {form.error}
    </p>{/if}{#if page.url.searchParams.has('saved')}<p role="status">
      Template saved locally.
    </p>{/if}
  <div class="mp-columns">
    <section class="mp-panel mp-form">
      <h2>Practice templates</h2>
      {#each data.info.templates as template (template.id)}<article class="mp-followup">
          <h3>{template.title} · {template.active ? 'Active' : 'Archived'}</h3>
          <p class="template-body">{template.body}</p>
          {#if data.info.can_manage}<form method="POST" action="?/state">
              <input type="hidden" name="id" value={template.id} /><input
                type="hidden"
                name="revision"
                value={template.revision}
              /><input type="hidden" name="active" value={String(!template.active)} /><button
                >{template.active ? 'Archive' : 'Reactivate'} template</button
              >
            </form>{/if}
        </article>{:else}<p>No templates recorded yet.</p>{/each}
    </section>
    {#if data.info.can_manage}<section class="mp-panel mp-form">
        <h2>Add a template</h2>
        <form method="POST" action="?/create" class="mp-form">
          <input
            type="hidden"
            name="request_id"
            value={form?.values?.request_id || data.requestKey}
          /><label
            >Title<input
              name="title"
              required
              maxlength="100"
              value={form?.values?.title || ''}
            /></label
          ><label
            >Text<textarea name="body" required maxlength="5000" rows="8"
              >{form?.values?.body || ''}</textarea
            ></label
          ><button class="mp-button">Save local template</button>
        </form>
      </section>{/if}
  </div>
  <RecordPages pages={data.info.pages} />
</div>

<style>
  .template-body {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
</style>
