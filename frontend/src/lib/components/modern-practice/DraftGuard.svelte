<script>
  import { onMount } from 'svelte';
  import { afterNavigate, beforeNavigate } from '$app/navigation';

  /** @type {{ dirty: boolean, draftForm: HTMLFormElement | undefined }} */
  let { dirty, draftForm } = $props();
  let submitting = false;
  const discardMessage = 'Discard your unsaved draft? Choose Cancel to keep editing.';

  beforeNavigate((navigation) => {
    if (!dirty || submitting) return;
    const from = navigation.from?.url;
    const to = navigation.to?.url;
    if (
      !navigation.willUnload &&
      from &&
      to &&
      from.origin === to.origin &&
      from.pathname === to.pathname &&
      from.search === to.search
    )
      return;
    if (navigation.willUnload || !window.confirm(discardMessage)) navigation.cancel();
  });
  afterNavigate(() => {
    submitting = false;
  });

  onMount(() => {
    /** @param {SubmitEvent} event */
    function submit(event) {
      if (event.defaultPrevented) return;
      if (dirty && event.target !== draftForm && !window.confirm(discardMessage)) {
        event.preventDefault();
        return;
      }
      // Native form posts unload this page. Saving the draft must remain possible.
      submitting = true;
      queueMicrotask(() => {
        if (event.defaultPrevented) submitting = false;
      });
    }
    function restore() {
      submitting = false;
    }
    document.addEventListener('submit', submit, true);
    window.addEventListener('pageshow', restore);
    return () => {
      document.removeEventListener('submit', submit, true);
      window.removeEventListener('pageshow', restore);
    };
  });
</script>

<p role="status">
  {dirty ? 'Unsaved draft — save before leaving.' : 'Draft matches the saved version.'}
</p>
