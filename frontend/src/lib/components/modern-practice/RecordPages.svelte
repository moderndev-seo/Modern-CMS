<script>
  import { page } from '$app/state';
  import { SvelteURLSearchParams } from 'svelte/reactivity';
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  let { pages } = $props();
  function destination(parameter, number) {
    const query = new SvelteURLSearchParams(page.url.searchParams);
    query.set(parameter, String(number));
    query.delete('saved');
    return asInternalPath(`${page.url.pathname}?${query}`);
  }
</script>

{#if pages.some((item) => item.count > item.size || item.page > 1)}
  <aside class="mp-panel mp-form" aria-label="Record pages">
    <p>Changing pages discards unsaved form changes.</p>
    {#each pages.filter((item) => item.count > item.size || item.page > 1) as item (item.parameter)}<nav
        class="mp-patient-links"
        aria-label={`${item.label} pages`}
      >
        <span
          >{item.label} · Page {item.page} of {Math.max(1, Math.ceil(item.count / item.size))} · {item.count}
          records</span
        >{#if item.page > 1}<a href={resolve(destination(item.parameter, item.page - 1))}
            >Previous {item.label.toLowerCase()}</a
          >{/if}{#if item.page * item.size < item.count}<a
            href={resolve(destination(item.parameter, item.page + 1))}
            >Next {item.label.toLowerCase()}</a
          >{/if}
      </nav>{/each}
  </aside>
{/if}
