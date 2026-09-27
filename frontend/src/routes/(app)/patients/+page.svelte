<script>
  import { resolve } from '$app/paths';
  import { asInternalPath } from '$lib/utils/paths.js';
  import { sourceLabel, dateTime } from '$lib/modern-practice.js';
  let { data } = $props();
</script>

<svelte:head><title>Patients | Modern Practice</title></svelte:head>
<div class="mp-page">
  <header class="mp-header">
    <div>
      <p class="mp-eyebrow">From first touch to care</p>
      <h1>Patients</h1>
      <p class="mp-muted">One patient. Every milestone. The original source stays with them.</p>
    </div>
    <a class="mp-button" href={resolve('/patients/new')}>Add patient</a>
  </header>
  {#if data.org.name.startsWith('TEST -')}<p class="mp-demo">
      Fictional test practice · demonstration records only
    </p>{/if}
  <section class="mp-panel">
    <div class="mp-panel-heading">
      <h2>Patient journeys <span class="mp-badge">{data.patients.count}</span></h2>
      <form class="mp-search" method="GET">
        <label class="mp-sr" for="patient-search">Search patients</label><input
          id="patient-search"
          name="search"
          value={data.search}
          placeholder="Search name or email"
        /><button class="mp-button secondary">Search</button>
      </form>
    </div>
    <div class="mp-table-wrap">
      <table class="mp-table">
        <thead
          ><tr
            ><th>Patient</th><th>Original source</th><th>Campaign</th><th>Known lead</th><th
            ></th></tr
          ></thead
        ><tbody>
          {#each data.patients.results as patient (patient.id)}<tr
              ><td
                ><a class="mp-person" href={resolve(asInternalPath(`/patients/${patient.id}`))}
                  ><span class="mp-avatar">{patient.name.slice(0, 1)}</span><span
                    ><strong>{patient.name}</strong><small
                      >{patient.contact_email || 'No email recorded'}</small
                    ></span
                  ></a
                ></td
              ><td><span class="mp-source">{sourceLabel(patient.original_source)}</span></td><td
                >{patient.original_campaign || 'Not recorded'}</td
              ><td>{dateTime(patient.lead_at)}</td><td
                ><a href={resolve(asInternalPath(`/patients/${patient.id}`))}>Open journey →</a></td
              ></tr
            >{:else}<tr
              ><td colspan="5" class="mp-empty"
                >No patient journeys found. Add a patient to start recording their source and care.</td
              ></tr
            >{/each}
        </tbody>
      </table>
    </div>
    <div class="mp-pagination">
      <span>Page {data.patients.page} · up to 50 patients per page</span
      >{#if data.patients.page > 1}<a
          href={resolve(
            asInternalPath(
              `/patients?search=${encodeURIComponent(data.search || '')}&page=${data.patients.page - 1}`
            )
          )}>Previous</a
        >{/if}{#if data.patients.page * 50 < data.patients.count}<a
          href={resolve(
            asInternalPath(
              `/patients?search=${encodeURIComponent(data.search || '')}&page=${data.patients.page + 1}`
            )
          )}>Next</a
        >{/if}
    </div>
  </section>
  <p class="mp-muted">
    Existing CRM contacts remain available under <a href={resolve('/contacts')}>Contacts</a>. A
    patient journey extends a contact; existing contacts are never automatically reclassified.
  </p>
</div>
