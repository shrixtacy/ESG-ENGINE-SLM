/**
 * ESGPilot SDK — Nudge Manager.
 *
 * Controls when and how often the nudge popup appears.
 * Rate limits: max 1 nudge per form-section per 5 minutes.
 * User can mute for the session.
 */

import type { NudgePayload } from '../types';

const NUDGE_COOLDOWN_MS = 5 * 60 * 1000; // 5 minutes

export class NudgeManager {
  /** section → last shown timestamp */
  private lastShown: Map<string, number> = new Map();
  private mutedForSession = false;
  private onShowCallback?: (payload: NudgePayload) => void;
  private onDismissCallback?: () => void;

  onShow(cb: (payload: NudgePayload) => void): void {
    this.onShowCallback = cb;
  }

  onDismiss(cb: () => void): void {
    this.onDismissCallback = cb;
  }

  /**
   * Propose showing a nudge for a section.
   * Returns true if nudge was shown, false if suppressed.
   */
  propose(section: string, payload: NudgePayload): boolean {
    if (this.mutedForSession) return false;
    if (!payload.hasFindings) return false;

    const last = this.lastShown.get(section) ?? 0;
    const now = Date.now();

    if (now - last < NUDGE_COOLDOWN_MS) return false;

    this.lastShown.set(section, now);
    this.onShowCallback?.(payload);
    return true;
  }

  dismiss(): void {
    this.onDismissCallback?.();
  }

  muteSession(): void {
    this.mutedForSession = true;
  }

  unmuteSession(): void {
    this.mutedForSession = false;
  }

  isMuted(): boolean {
    return this.mutedForSession;
  }

  resetCooldown(section: string): void {
    this.lastShown.delete(section);
  }
}
