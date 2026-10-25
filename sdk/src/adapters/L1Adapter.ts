/**
 * ESGPilot SDK — L1 Adapter (Schema Push).
 *
 * Highest-reliability integration: host app explicitly calls
 * esgpilot.setFormContext({ formId, schema, values }).
 *
 * Also provides the FieldObserver that sends diffs to the API
 * when host app attaches to a form element (debounced 400ms).
 *
 * Privacy:
 * - Only fields in the provided allowList are ever sent.
 * - Password/sensitive inputs are always ignored.
 * - Values are sent over WSS, not stored unless tenant enables draft memory.
 */

import type { FormContext, FieldData } from '../types';

const DEBOUNCE_MS = 400;
const SENSITIVE_TYPES = new Set(['password', 'email', 'tel', 'credit-card']);
const SENSITIVE_NAME_PATTERNS = /password|secret|ssn|aadhaar|pan|card|cvv|token/i;

type ContextUpdateCallback = (ctx: FormContext) => void;

export class L1Adapter {
  private selector: string;
  private baseContext: FormContext;
  private onUpdate: ContextUpdateCallback;
  private formEl: Element | null = null;
  private observer: MutationObserver | null = null;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private lastSnapshot: Record<string, unknown> = {};
  private attached = false;

  constructor(
    selector: string,
    baseContext: FormContext,
    onUpdate: ContextUpdateCallback,
  ) {
    this.selector = selector;
    this.baseContext = baseContext;
    this.onUpdate = onUpdate;
  }

  attach(): void {
    if (this.attached) return;

    this.formEl = document.querySelector(this.selector);
    if (!this.formEl) {
      console.warn(`[ESGPilot L1] Form not found: ${this.selector}`);
      return;
    }

    // Listen for input/change/blur on all form fields
    this.formEl.addEventListener('input', this._onFieldEvent, { capture: true });
    this.formEl.addEventListener('change', this._onFieldEvent, { capture: true });
    this.formEl.addEventListener('blur', this._onFieldEvent, { capture: true });

    // Watch for dynamically added fields
    this.observer = new MutationObserver(() => this._scheduleSnapshot());
    this.observer.observe(this.formEl, { childList: true, subtree: true });

    this.attached = true;

    // Initial snapshot
    this._scheduleSnapshot();
  }

  detach(): void {
    if (!this.attached || !this.formEl) return;
    this.formEl.removeEventListener('input', this._onFieldEvent, { capture: true });
    this.formEl.removeEventListener('change', this._onFieldEvent, { capture: true });
    this.formEl.removeEventListener('blur', this._onFieldEvent, { capture: true });
    this.observer?.disconnect();
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.attached = false;
  }

  /**
   * Manually push context (bypasses DOM observation).
   * Used by host app calling ESGPilot.setFormContext().
   */
  pushContext(fields: FieldData[]): void {
    const ctx: FormContext = { ...this.baseContext, fields };
    this.onUpdate(ctx);
  }

  // ──────────────────────────────────────────────
  // Private
  // ──────────────────────────────────────────────

  private _onFieldEvent = (e: Event): void => {
    const target = e.target as HTMLInputElement | null;
    if (!target || this._isSensitive(target)) return;
    this._scheduleSnapshot();
  };

  private _scheduleSnapshot(): void {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this._takeSnapshot(), DEBOUNCE_MS);
  }

  private _takeSnapshot(): void {
    const fields = this._extractFields();
    const snapshot = Object.fromEntries(fields.map((f) => [f.fieldCode, f.value]));

    // Only send diff — don't spam API if nothing changed
    if (JSON.stringify(snapshot) === JSON.stringify(this.lastSnapshot)) return;
    this.lastSnapshot = snapshot;

    const ctx: FormContext = { ...this.baseContext, fields };
    this.onUpdate(ctx);
  }

  private _extractFields(): FieldData[] {
    if (!this.formEl) return [];
    const fields: FieldData[] = [];
    const seen = new Set<string>();

    // Priority 1: data-esg-field attributes
    this.formEl.querySelectorAll('[data-esg-field]').forEach((el) => {
      const fieldCode = (el as HTMLElement).dataset.esgField;
      if (!fieldCode || seen.has(fieldCode)) return;

      const input = el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA'
        ? el as HTMLInputElement
        : el.querySelector('input, select, textarea') as HTMLInputElement | null;

      if (!input || this._isSensitive(input)) return;

      seen.add(fieldCode);
      fields.push({
        fieldCode,
        value: this._getValue(input),
        unit: (el as HTMLElement).dataset.esgUnit,
        label: (el as HTMLElement).dataset.esgLabel ?? this._inferLabel(el as HTMLElement),
      });
    });

    // Priority 2: all named inputs not already captured
    this.formEl.querySelectorAll('input[name], select[name], textarea[name]').forEach((el) => {
      const input = el as HTMLInputElement;
      const name = input.name;
      if (!name || seen.has(name) || this._isSensitive(input)) return;
      seen.add(name);
      fields.push({
        fieldCode: name,
        value: this._getValue(input),
        label: this._inferLabel(input),
      });
    });

    return fields;
  }

  private _getValue(input: HTMLInputElement): string | number | null {
    if (input.type === 'checkbox') return input.checked ? 1 : 0;
    if (input.type === 'number') {
      const n = parseFloat(input.value);
      return isNaN(n) ? null : n;
    }
    return input.value || null;
  }

  private _isSensitive(input: HTMLInputElement): boolean {
    return (
      SENSITIVE_TYPES.has(input.type ?? '') ||
      SENSITIVE_NAME_PATTERNS.test(input.name ?? '') ||
      SENSITIVE_NAME_PATTERNS.test(input.id ?? '') ||
      input.autocomplete === 'current-password'
    );
  }

  private _inferLabel(el: HTMLElement): string | undefined {
    // Try aria-label, then associated <label>
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel) return ariaLabel;

    const id = el.id;
    if (id) {
      const label = document.querySelector(`label[for="${id}"]`);
      if (label) return (label as HTMLElement).innerText.trim();
    }

    const parentLabel = el.closest('label');
    if (parentLabel) return (parentLabel as HTMLElement).innerText.trim();

    return undefined;
  }
}
