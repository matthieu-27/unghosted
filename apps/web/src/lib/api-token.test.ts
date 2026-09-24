import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ getApiToken: vi.fn() }));

vi.mock('@/lib/auth-server', () => ({ getApiToken: h.getApiToken }));

import { clearApiToken, fetchApiToken } from './api-token';

beforeEach(() => {
  h.getApiToken.mockReset();
  clearApiToken();
});

describe('fetchApiToken', () => {
  it('asks the server once and reuses the cached token', async () => {
    h.getApiToken.mockResolvedValue('token-1');

    await expect(fetchApiToken()).resolves.toBe('token-1');
    await expect(fetchApiToken()).resolves.toBe('token-1');
    expect(h.getApiToken).toHaveBeenCalledTimes(1);
  });

  it('shares one round trip between concurrent callers', async () => {
    h.getApiToken.mockResolvedValue('token-1');

    const [first, second] = await Promise.all([
      fetchApiToken(),
      fetchApiToken(),
    ]);

    expect(first).toBe('token-1');
    expect(second).toBe('token-1');
    expect(h.getApiToken).toHaveBeenCalledTimes(1);
  });

  it('asks again after the cache is cleared', async () => {
    h.getApiToken.mockResolvedValueOnce('token-1');
    h.getApiToken.mockResolvedValueOnce('token-2');

    await fetchApiToken();
    clearApiToken();

    await expect(fetchApiToken()).resolves.toBe('token-2');
    expect(h.getApiToken).toHaveBeenCalledTimes(2);
  });

  it('caches nothing when nobody is signed in', async () => {
    h.getApiToken.mockResolvedValue(null);

    await expect(fetchApiToken()).resolves.toBeNull();
    await expect(fetchApiToken()).resolves.toBeNull();
    expect(h.getApiToken).toHaveBeenCalledTimes(2);
  });
});
