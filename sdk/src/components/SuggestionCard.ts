/**
 * ESGPilot SDK — Suggestion Card Web Component.
 *
 * Standalone card for rendering a single suggestion.
 * Used in the panel and can also be embedded inline by host apps.
 *
 * Usage:
 *   <esgpilot-suggestion-card
 *     id="rec_001"
 *     severity="warn"
 *     title="Scope 2 emissions 240% higher YoY"
 *     why="..."
 *     how-to-fix="..."
 *   ></esgpilot-suggestion-card>
 */

import type { SuggestionCard as SuggestionCardData } from '../types';

const SEV_COLORS: Record<string, string> = {
  critical: '#dc2626',
  warn: '#d97706',
  info: '#2563eb',
};

const SEV_ICONS: Record<string, string> = {
  critical: '🔴',
  warn: '🟡',
  info: '🔵',
};

export class SuggestionCardElement extends HTMLElement {
  static get observedAttributes() {
    return ['severity', 'title', 'why', 'how-to-fix', 'field-code', 'confidence'];
  }

  private _data: Partial<SuggestionCardData> = {};

  connectedCallback(): void {
    this._data = {
      id: this.getAttribute('card-id') ?? '',
      severity: (this.getAttribute('severity') as 'info' | 'warn' | 'critical') ?? 'info',
      title: this.getAttribute('title') ?? '',
      why: this.getAttribute('why') ?? undefined,
      howToFix: this.getAttribute('how-to-fix') ?? undefined,
      fieldCode: this.getAttribute('field-code') ?? undefined,
      confidence: parseFloat(this.getAttribute('confidence') ?? '0'),
    };
    this._render();
  }

  attributeChangedCallback(): void {
    if (this.isConnected) this.connectedCallback();
  }

  setData(data: SuggestionCardData): void {
    this._data = data;
    this._render();
  }

  private _render(): void {
    const sev = this._data.severity ?? 'info';
    const color = SEV_COLORS[sev] ?? '#2563eb';
    const icon = SEV_ICONS[sev] ?? '🔵';

    this.innerHTML = `
      <style>
        .sc-card {
          border: 1px solid #e5e7eb;
          border-left: 4px solid ${color};
          border-radius: 10px;
          padding: 12px 16px;
          margin: 0 0 10px;
          font-family: system-ui, -apple-system, sans-serif;
          background: #fff;
        }
        .sc-header { display:flex; align-items:flex-start; gap:8px; margin-bottom:6px; }
        .sc-icon { font-size: 14px; line-height: 1.5; flex-shrink: 0; }
        .sc-title { font-size:13px; font-weight:600; color:#111827; flex:1; }
        .sc-why { font-size:12px; color:#6b7280; margin-bottom:6px; line-height:1.5; }
        .sc-fix { font-size:12px; color:#374151; line-height:1.5; }
        .sc-fix strong { font-weight:600; }
        .sc-refs { margin-top:8px; display:flex; flex-wrap:wrap; gap:4px; }
        .sc-ref { font-size:11px; background:#f3f4f6; padding:2px 7px; border-radius:4px; color:#6b7280; }
        .sc-actions { display:flex; gap:8px; margin-top:10px; }
        .sc-btn {
          padding:5px 12px; border-radius:6px; font-size:11px; font-weight:600;
          cursor:pointer; border:1px solid #d1d5db; background:#fff; color:#374151;
          transition: background 0.1s;
        }
        .sc-btn:hover { background:#f9fafb; }
        .sc-btn-jump { border-color: ${color}; color: ${color}; }
        .sc-confidence { font-size:10px; color:#9ca3af; margin-top:6px; }
      </style>
      <div class="sc-card" role="article" aria-label="Suggestion: ${this._data.title}">
        <div class="sc-header">
          <span class="sc-icon" aria-hidden="true">${icon}</span>
          <div class="sc-title">${this._data.title ?? ''}</div>
        </div>
        ${this._data.why ? `<div class="sc-why">${this._data.why}</div>` : ''}
        ${this._data.howToFix ? `
          <div class="sc-fix">
            <strong>How to fix:</strong> ${this._data.howToFix}
          </div>
        ` : ''}
        ${this._data.references?.length ? `
          <div class="sc-refs">
            ${this._data.references.map((r) =>
              `<span class="sc-ref">${r.doc}${r.section ? ' · ' + r.section : ''}</span>`
            ).join('')}
          </div>
        ` : ''}
        <div class="sc-actions">
          ${this._data.fieldCode ? `
            <button class="sc-btn sc-btn-jump" data-field="${this._data.fieldCode}" aria-label="Jump to this field in the form">
              ↗ Jump to field
            </button>
          ` : ''}
          <button class="sc-btn sc-btn-accept" aria-label="Mark as accepted">✓ Accept</button>
          <button class="sc-btn" aria-label="Dismiss suggestion">✕ Dismiss</button>
        </div>
        ${this._data.confidence ? `
          <div class="sc-confidence">Confidence: ${(this._data.confidence * 100).toFixed(0)}%</div>
        ` : ''}
      </div>
    `;

    this.querySelector('.sc-btn-jump')?.addEventListener('click', () => {
      this.dispatchEvent(new CustomEvent('jump-to-field', {
        bubbles: true,
        composed: true,
        detail: { fieldCode: this._data.fieldCode },
      }));
    });

    this.querySelector('.sc-btn-accept')?.addEventListener('click', () => {
      this.dispatchEvent(new CustomEvent('suggestion-accepted', {
        bubbles: true,
        composed: true,
        detail: { id: this._data.id },
      }));
    });
  }
}
