import { describe, it, expect, vi, beforeEach } from 'vitest';
vi.mock('$lib/api-helpers.js', () => ({ apiRequest: vi.fn() }));
import { apiRequest } from '$lib/api-helpers.js';
import { readPractice, writePractice } from './modern-practice.js';

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
});

describe('patient server proxy authorization', () => {
  for (const status of [401, 403, 404]) {
    it(`propagates a denied read (${status}) without patient data`, async () => {
      vi.mocked(apiRequest).mockRejectedValue({ status, message: 'Denied' });
      const event = /** @type {any} */ ({ cookies: {} });
      await expect(readPractice(event, 'patient/')).rejects.toMatchObject({ status });
    });
    it(`propagates a denied form write (${status}) without success`, async () => {
      vi.mocked(apiRequest).mockRejectedValue({ status, message: 'Denied' });
      const form = new FormData();
      form.set('kind', 'treated');
      form.set('org', 'forged');
      const event = /** @type {any} */ ({ cookies: {}, request: { formData: async () => form } });
      const result = await writePractice(event, 'patient/events/', ['kind']);
      expect(result).toMatchObject({ status, data: { error: 'Denied' } });
      expect(apiRequest).toHaveBeenCalledWith(
        '/patients/patient/events/',
        { method: 'POST', body: { kind: 'treated' } },
        event.cookies
      );
    });
  }
});
