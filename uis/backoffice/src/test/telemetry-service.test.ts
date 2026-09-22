import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TelemetryService } from '../services/telemetry';

describe('TelemetryService Unit Tests', () => {
  let service: TelemetryService;
  let fetchMock: ReturnType<typeof vi.fn>;
  let sendBeaconMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();

    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ received: 1 }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    sendBeaconMock = vi.fn().mockReturnValue(true);
    Object.defineProperty(global.navigator, 'sendBeacon', {
      value: sendBeaconMock,
      writable: true,
      configurable: true,
    });

    service = new TelemetryService({
      endpoint: 'http://localhost:8000/telemetry/events',
      batchSize: 20,
      flushIntervalMs: 10000,
      maxRetries: 3,
      retryBaseDelayMs: 100, // fast retries in tests
      debug: true,
    });
  });

  afterEach(() => {
    service.destroy();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('completes the event envelope with required metadata', () => {
    service.setUserContext('9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d');

    service.track('inbound_order_created', {
      order_id: '11111111-2222-3333-4444-555555555555',
      local_id: 'MED-001',
      ingredient_id: '66666666-7777-8888-9999-000000000000',
      ingredient_sku: 'ING-001',
      quantity: 15.0,
      unit_of_measure: 'kg',
      previous_stock: 5.0,
      resulting_stock: 20.0,
    });

    const queue = service.getQueue();
    expect(queue.length).toBe(1);

    const event = queue[0];
    expect(event.eventId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    expect(event.requestId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    expect(event.timestamp).toBeTruthy();
    expect(new Date(event.timestamp).toISOString()).toBe(event.timestamp);
    expect(event.schemaVersion).toBe('1.0.0');
    expect(event.event_type).toBe('inbound_order_created');
    expect(event.entity_action).toBe('created');
    expect(event.userId).toBe('9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d');
    expect(event.sessionId).toBeTruthy();
  });

  it('does not trigger flush at 19 events, but triggers immediately at 20 events', async () => {
    for (let i = 0; i < 19; i++) {
      service.track('backoffice_page_viewed', {
        previous_route: 'DIRECT_ENTRY',
        current_route: `/route-${i}`,
        navigation_duration_ms: 100,
      });
    }

    expect(service.getQueue().length).toBe(19);
    expect(fetchMock).not.toHaveBeenCalled();

    // 20th event triggers flush
    service.track('backoffice_page_viewed', {
      previous_route: 'DIRECT_ENTRY',
      current_route: '/route-19',
      navigation_duration_ms: 100,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.events.length).toBe(20);

    // Let promise resolve
    await vi.runAllTimersAsync();
    expect(service.getQueue().length).toBe(0);
  });

  it('triggers flush after 10 seconds timer expires from first pending event', async () => {
    service.track('backoffice_page_viewed', {
      previous_route: 'DIRECT_ENTRY',
      current_route: '/backoffice/overview',
      navigation_duration_ms: 250,
    });

    expect(fetchMock).not.toHaveBeenCalled();

    // Advance 5 seconds — still not called
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchMock).not.toHaveBeenCalled();

    // Advance remaining 5 seconds — 10s elapsed, flush triggered
    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('removes successful batch from queue upon 2xx response', async () => {
    service.track('backoffice_page_viewed', {
      previous_route: 'DIRECT_ENTRY',
      current_route: '/backoffice/overview',
      navigation_duration_ms: 250,
    });

    expect(service.getQueue().length).toBe(1);

    await service.flush();
    expect(service.getQueue().length).toBe(0);
  });

  it('retries up to 3 times on failure preserving original eventId', async () => {
    fetchMock.mockRejectedValue(new Error('Network error'));

    service.track('backoffice_page_viewed', {
      previous_route: 'DIRECT_ENTRY',
      current_route: '/backoffice/overview',
      navigation_duration_ms: 250,
    });

    const initialEventId = service.getQueue()[0].eventId;

    const flushPromise = service.flush();
    await vi.runAllTimersAsync();
    await flushPromise;

    // Initial attempt + 3 retries = 4 total calls
    expect(fetchMock).toHaveBeenCalledTimes(4);

    // Verify all attempts sent the exact same eventId
    for (let callIndex = 0; callIndex < 4; callIndex++) {
      const callBody = JSON.parse(fetchMock.mock.calls[callIndex][1].body);
      expect(callBody.events[0].eventId).toBe(initialEventId);
    }

    // After exhausting max retries, discarded
    expect(service.getQueue().length).toBe(0);
  });

  it('does not duplicate events when two flushes are initiated simultaneously', async () => {
    service.track('backoffice_page_viewed', {
      previous_route: 'DIRECT_ENTRY',
      current_route: '/backoffice/overview',
      navigation_duration_ms: 250,
    });

    // Invoke flush twice concurrently
    const p1 = service.flush();
    const p2 = service.flush();

    await Promise.all([p1, p2]);

    // Only one network request was executed
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('uses sendBeacon on visibilitychange to hidden or pagehide', () => {
    service.track('backoffice_page_viewed', {
      previous_route: 'DIRECT_ENTRY',
      current_route: '/backoffice/overview',
      navigation_duration_ms: 250,
    });

    expect(service.getQueue().length).toBe(1);

    // Simulate pagehide
    service.flushBeacon();

    expect(sendBeaconMock).toHaveBeenCalledTimes(1);
    expect(sendBeaconMock.mock.calls[0][0]).toBe('http://localhost:8000/telemetry/events');
    expect(service.getQueue().length).toBe(0);
  });

  it('falls back to keepalive fetch when sendBeacon returns false or fails', () => {
    sendBeaconMock.mockReturnValue(false); // sendBeacon failed/rejected

    service.track('backoffice_page_viewed', {
      previous_route: 'DIRECT_ENTRY',
      current_route: '/backoffice/overview',
      navigation_duration_ms: 250,
    });

    service.flushBeacon();

    expect(sendBeaconMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/telemetry/events',
      expect.objectContaining({
        keepalive: true,
        method: 'POST',
      })
    );
  });

  it('rejects unapproved extra properties in development mode', () => {
    expect(() => {
      service.track('backoffice_page_viewed', {
        previous_route: 'DIRECT_ENTRY',
        current_route: '/backoffice/overview',
        navigation_duration_ms: 250,
        // @ts-expect-error Testing defensive runtime rejection of extra props
        unapproved_property: 'dangerous_leak',
      });
    }).toThrow(/Disallowed property "unapproved_property"/);
  });

  it('functions safely without accessing browser globals during SSR', () => {
    const originalWindow = global.window;
    // @ts-expect-error Simulating SSR environment
    delete global.window;

    const ssrService = new TelemetryService({ debug: false });
    expect(() => {
      ssrService.track('backoffice_page_viewed', {
        previous_route: 'DIRECT_ENTRY',
        current_route: '/backoffice/overview',
        navigation_duration_ms: 100,
      });
    }).not.toThrow();

    const queue = ssrService.getQueue();
    expect(queue.length).toBe(1);
    expect(queue[0].sessionId).toBeNull();

    // Restore window
    global.window = originalWindow;
    ssrService.destroy();
  });

  it('does not cause recursion on telemetry endpoint errors', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    service.track('backoffice_page_viewed', {
      previous_route: 'DIRECT_ENTRY',
      current_route: '/backoffice/overview',
      navigation_duration_ms: 100,
    });

    const flushPromise = service.flush();
    await vi.runAllTimersAsync();
    await flushPromise;

    // Queue is clean and no infinite loop was created
    expect(service.getQueue().length).toBe(0);
  });
});
