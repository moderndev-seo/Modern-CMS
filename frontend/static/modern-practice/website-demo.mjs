import { createWebsiteAttribution, leadAttribution } from './website-attribution.mjs';

const adapter = createWebsiteAttribution({
  siteId: 'fictional-demo',
  pages: ['https://example.com/'],
  sourceRules: [
    { source: 'google', medium: 'cpc', value: 'google_ads' },
    { source: 'newsletter', medium: 'email', value: 'email' }
  ],
  campaigns: { test: 'TEST campaign' }
});
const element = (id) => document.getElementById(id);
function visit(url) {
  const result = adapter.capture({ consent: element('consent').value, url });
  element('lead').textContent = JSON.stringify(leadAttribution(result), null, 2);
  element('observations').textContent = JSON.stringify(result, null, 2);
  element('status').textContent =
    result.status === 'captured'
      ? 'Captured locally. No CRM record was created.'
      : 'No capture: explicit consent is required. Local observations were cleared.';
}
element('paid').addEventListener('click', () =>
  visit('https://example.com/?utm_source=google&utm_medium=cpc&utm_campaign=test')
);
element('email').addEventListener('click', () =>
  visit('https://example.com/?utm_source=newsletter&utm_medium=email')
);
element('unknown').addEventListener('click', () => visit('https://example.com/'));
element('consent').addEventListener('change', () => {
  if (element('consent').value !== 'granted') visit('https://example.com/');
});
element('reset').addEventListener('click', () => {
  adapter.clear();
  element('lead').textContent = '{"original_source":"unknown"}';
  element('observations').textContent = 'No observations captured.';
  element('status').textContent = 'Demo cleared. Simulate a new introduction.';
});
