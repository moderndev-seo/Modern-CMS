<script>
  import { resolve } from '$app/paths';
  let { data } = $props();
</script>

<svelte:head><title>{data.moduleName} | Modern Practice</title></svelte:head>
<div class="mp-page mp-narrow">
  <p class="mp-eyebrow">Modern Practice</p>
  <h1>{data.moduleName}</h1>
  <section class="mp-panel mp-form">
    <span class="mp-badge">Not implemented</span>
    <h2>This module is planned.</h2>
    <p>
      Milestone one covers Patients and Growth. No live messaging or review services are connected.
    </p>
    <a class="mp-button" href={resolve('/patients')}>Open Patients</a>
  </section>
</div>
