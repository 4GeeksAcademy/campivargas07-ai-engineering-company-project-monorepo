/**
 * telemetry.ts — Centralized Telemetry Service for Brasaland Backoffice
 *
 * Implements Phase 2 Telemetry:
 * - Strictly typed event capture restricted to approved contract
 * - Auto-populated envelope (UUID eventId, UTC ISO timestamp, session, user, SemVer, correlation requestId)
 * - Local in-memory queue with batching (10s debounce or 20 events)
 * - Reliable unload/hide flush via sendBeacon with keepalive fetch fallback
 * - Exponential backoff retry with jitter preserving original eventId
 * - Zero PII and strict SSR safety
 */

import {
  SCHEMA_VERSION,
  EVENT_ACTION_MAPPING,
  EVENT_ALLOWLISTS,
  type EventType,
  type EventPropertiesMap,
  type AnyTelemetryEnvelope,
} from '@/types/telemetry';

export interface TelemetryConfig {
  endpoint?: string;
  batchSize?: number;
  flushIntervalMs?: number;
  maxRetries?: number;
  retryBaseDelayMs?: number;
  debug?: boolean;
}

const DEFAULT_BATCH_SIZE = 20;
const DEFAULT_FLUSH_INTERVAL_MS = 10000; // 10 seconds
const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_RETRY_BASE_DELAY_MS = 1000;
const SESSION_STORAGE_KEY = 'brasaland_telemetry_session_id';

export class TelemetryService {
  private endpoint: string;
  private batchSize: number;
  private flushIntervalMs: number;
  private maxRetries: number;
  private retryBaseDelayMs: number;
  private debug: boolean;

  private queue: AnyTelemetryEnvelope[] = [];
  private timer: ReturnType<typeof setTimeout> | null = null;
  private isFlushing = false;
  private userId: string | null = null;
  private sessionId: string | null = null;
  private listenersAttached = false;
  private cleanupListeners: (() => void) | null = null;

  constructor(config: TelemetryConfig = {}) {
    this.endpoint =
      config.endpoint ||
      (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT) ||
      '/api/telemetry/events';
    this.batchSize = config.batchSize ?? DEFAULT_BATCH_SIZE;
    this.flushIntervalMs = config.flushIntervalMs ?? DEFAULT_FLUSH_INTERVAL_MS;
    this.maxRetries = config.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.retryBaseDelayMs = config.retryBaseDelayMs ?? DEFAULT_RETRY_BASE_DELAY_MS;
    this.debug = config.debug ?? (typeof process !== 'undefined' && process.env.NODE_ENV !== 'production');
  }

  /**
   * Sets authenticated user context (seudonimizado internal UUID).
   */
  public setUserContext(userId: string | null): void {
    this.userId = userId;
  }

  /**
   * Clears authenticated user context on logout.
   */
  public clearUserContext(): void {
    this.userId = null;
  }

  /**
   * Generates a secure UUID v4 string.
   */
  private generateUUID(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      try {
        return crypto.randomUUID();
      } catch {
        // Fallback if crypto.randomUUID is restricted
      }
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /**
   * Deferred browser session ID resolution. Never uses JWT or localStorage.
   */
  private getSessionId(): string | null {
    if (typeof window === 'undefined') {
      return null;
    }
    if (this.sessionId) {
      return this.sessionId;
    }
    try {
      const existing = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (existing) {
        this.sessionId = existing;
        return existing;
      }
      const newSessionId = this.generateUUID();
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
      this.sessionId = newSessionId;
      return newSessionId;
    } catch {
      // In private browsing or storage-disabled modes, maintain in-memory ID
      if (!this.sessionId) {
        this.sessionId = this.generateUUID();
      }
      return this.sessionId;
    }
  }

  /**
   * Attaches pagehide and visibilitychange listeners once on client.
   */
  public initBrowserListeners(): void {
    if (typeof window === 'undefined' || typeof document === 'undefined' || this.listenersAttached) {
      return;
    }
    this.listenersAttached = true;

    const handleVisibility = () => {
      if (document.visibilityState === 'hidden') {
        this.flushBeacon();
      }
    };

    const handlePageHide = () => {
      this.flushBeacon();
    };

    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('pagehide', handlePageHide);

    this.cleanupListeners = () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('pagehide', handlePageHide);
      this.listenersAttached = false;
    };
  }

  /**
   * Captures an approved telemetry event with strict typing and defensive validation.
   */
  public track<T extends EventType>(eventType: T, properties: EventPropertiesMap[T]): void {
    try {
      // Defensive runtime check against unapproved extra properties in development
      if (this.debug) {
        const allowlist = EVENT_ALLOWLISTS[eventType];
        if (allowlist && properties && typeof properties === 'object') {
          for (const key of Object.keys(properties)) {
            if (!allowlist.includes(key)) {
              console.warn(
                `[Telemetry] Disallowed property "${key}" for event "${eventType}". Discarding invalid property.`
              );
              throw new Error(`[Telemetry] Disallowed property "${key}" for event "${eventType}"`);
            }
          }
        }
      }

      const envelope: AnyTelemetryEnvelope = {
        eventId: this.generateUUID(),
        timestamp: new Date().toISOString(),
        sessionId: this.getSessionId(),
        userId: this.userId,
        event_type: eventType,
        entity_action: EVENT_ACTION_MAPPING[eventType] as any,
        schemaVersion: SCHEMA_VERSION,
        requestId: this.generateUUID(),
        properties: { ...properties } as any,
      };

      this.queue.push(envelope);

      // Lazily ensure unload listeners are bound
      this.initBrowserListeners();

      // Check batching triggers
      if (this.queue.length >= this.batchSize) {
        if (this.timer) {
          clearTimeout(this.timer);
          this.timer = null;
        }
        void this.flush();
      } else if (this.timer === null) {
        // Start 10-second timer from the first pending event
        this.timer = setTimeout(() => {
          this.timer = null;
          void this.flush();
        }, this.flushIntervalMs);
      }
    } catch (err) {
      if (this.debug) {
        // Re-throw in development when testing validation errors
        throw err;
      }
      // Never block user experience in production
    }
  }

  /**
   * Drains up to batchSize events from the queue and sends them to the endpoint.
   */
  public async flush(): Promise<boolean> {
    if (this.isFlushing || this.queue.length === 0) {
      return false;
    }

    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }

    this.isFlushing = true;
    const batch = this.queue.slice(0, this.batchSize);

    try {
      const success = await this.sendWithRetry(batch, 0);

      if (success) {
        // Remove only the events that were successfully delivered
        this.queue.splice(0, batch.length);
      } else {
        // Discard after max retries to prevent unbounded memory growth
        this.queue.splice(0, batch.length);
        if (this.debug) {
          console.warn('[Telemetry] Batch discarded after exceeding max retries.');
        }
      }
      return success;
    } catch {
      this.queue.splice(0, batch.length);
      return false;
    } finally {
      this.isFlushing = false;

      // If more events arrived during flush, schedule next batch
      if (this.queue.length > 0) {
        if (this.queue.length >= this.batchSize) {
          void this.flush();
        } else if (this.timer === null) {
          this.timer = setTimeout(() => {
            this.timer = null;
            void this.flush();
          }, this.flushIntervalMs);
        }
      }
    }
  }

  /**
   * Transmits batch with exponential backoff and small jitter, preserving original eventIds.
   */
  private async sendWithRetry(batch: AnyTelemetryEnvelope[], attempt: number): Promise<boolean> {
    try {
      const response = await fetch(this.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ events: batch }),
      });

      if (response.ok) {
        return true;
      }
    } catch {
      // Network failure
    }

    if (attempt < this.maxRetries) {
      const delay = Math.min(30000, this.retryBaseDelayMs * Math.pow(2, attempt)) + Math.random() * 250;
      await new Promise((resolve) => setTimeout(resolve, delay));
      return this.sendWithRetry(batch, attempt + 1);
    }

    return false;
  }

  /**
   * Synchronous or keepalive flush on unload/visibilitychange.
   */
  public flushBeacon(): void {
    if (this.queue.length === 0) {
      return;
    }

    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }

    while (this.queue.length > 0) {
      const batch = this.queue.splice(0, this.batchSize);
      let beaconSuccess = false;

      if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        try {
          const blob = new Blob([JSON.stringify({ events: batch })], { type: 'application/json' });
          beaconSuccess = navigator.sendBeacon(this.endpoint, blob);
        } catch {
          beaconSuccess = false;
        }
      }

      if (!beaconSuccess && typeof fetch !== 'undefined') {
        try {
          void fetch(this.endpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ events: batch }),
            keepalive: true,
          }).catch(() => {});
        } catch {
          // Ignore unload errors
        }
      }
    }
  }

  /**
   * Resets queue, timers, and listeners (primarily for test environments).
   */
  public destroy(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.cleanupListeners) {
      this.cleanupListeners();
      this.cleanupListeners = null;
    }
    this.queue = [];
    this.isFlushing = false;
    this.userId = null;
    this.sessionId = null;
  }

  /**
   * Returns a copy of the pending queue for testing and inspection.
   */
  public getQueue(): readonly AnyTelemetryEnvelope[] {
    return [...this.queue];
  }
}

// Global shared singleton instance
export const telemetryService = new TelemetryService();

