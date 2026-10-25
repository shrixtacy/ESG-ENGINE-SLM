/**
 * ESGPilot SDK — Main Orchestrator.
 *
 * Singleton that manages the widget lifecycle:
 *  - Session token acquisition
 *  - Transport connection
 *  - Form adapter attachment
 *  - Nudge triggering
 *  - Panel open/close
 *  - Event emission
 */

import type { SDKConfig, UserContext, FormConfig, FormContext, SDKEvent, NudgePayload } from '../types';
import { Transport } from './Transport';
import { NudgeManager } from './NudgeManager';

type EventListener = (event: SDKEvent) => void;

class ESGPilotSDKClass {
  private static _instance: ESGPilotSDKClass | null = null;

  private config!: Required<SDKConfig>;
  private transport!: Transport;
  private nudgeManager!: NudgeManager;
  private sessionToken = '';
  private user: UserContext | null = null;
  private listeners: EventListener[] = [];
  private widgetRoot: ShadowRoot | null = null;
  private panelOpen = false;
  private formAdapters: Map<string, import('../adapters/L1Adapter').L1Adapter> = new Map();

  private constructor() {}

  static getInstance(): ESGPilotSDKClass {
    if (!ESGPilotSDKClass._instance) {
      ESGPilotSDKClass._instance = new ESGPilotSDKClass();
    }
    return ESGPilotSDKClass._instance;
  }

  /**
   * Initialize the SDK.
   * Must be called before any other method.
   */
  init(config: SDKConfig): void {
    this.config = {
      apiUrl: 'https://api.esgpilot.io',
      position: 'bottom-right',
      lang: 'en',
      theme: {},
      ...config,
    };

    this.nudgeManager = new NudgeManager();
    this.nudgeManager.onShow((payload) => this._showNudge(payload));
    this.nudgeManager.onDismiss(() => this._dismissNudge());

    // Mount widget into DOM
    this._mountWidget();
  }

  /**
   * Set user context (called after login).
   */
  setUser(user: UserContext): void {
    this.user = user;
    this._acquireToken().catch(console.error);
  }

  /**
   * Attach SDK to a form element.
   * L1 integration: host app controls context.
   */
  async attachForm(
    selector: string,
    formConfig: FormConfig,
    formId?: string,
  ): Promise<void> {
    // Lazy-import adapters to keep initial bundle small
    const { L1Adapter } = await import('../adapters/L1Adapter');
    const id = formId ?? selector;
    const adapter = new L1Adapter(
      selector,
      { formId: id, framework: formConfig.framework, section: formConfig.section, fy: formConfig.fy ?? 'FY2025', fields: [] },
      (ctx) => this._onFormContextUpdate(ctx),
    );
    adapter.attach();
    this.formAdapters.set(id, adapter);
  }

  /**
   * Programmatically push form context (L1 schema push).
   */
  async setFormContext(ctx: FormContext): Promise<void> {
    await this._onFormContextUpdate(ctx);
  }

  /**
   * Open the suggestion panel.
   */
  openPanel(): void {
    if (this.panelOpen) return;
    this.panelOpen = true;
    this._renderPanel(true);
    this._emit({ type: 'panel_opened' });
  }

  closePanel(): void {
    if (!this.panelOpen) return;
    this.panelOpen = false;
    this._renderPanel(false);
    this._emit({ type: 'panel_closed' });
  }

  on(listener: EventListener): () => void {
    this.listeners.push(listener);
    return () => {
      const idx = this.listeners.indexOf(listener);
      if (idx >= 0) this.listeners.splice(idx, 1);
    };
  }

  destroy(): void {
    this.transport?.disconnect();
    this.widgetRoot?.host.remove();
    this.widgetRoot = null;
    this.formAdapters.forEach((a) => a.detach());
    this.formAdapters.clear();
    ESGPilotSDKClass._instance = null;
  }

  // ──────────────────────────────────────────────
  // Private
  // ──────────────────────────────────────────────

  private async _acquireToken(): Promise<void> {
    if (!this.user) return;
    try {
      const res = await fetch(`${this.config.apiUrl}/v1/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenant_key: this.config.key,
          user_id: this.user.id,
          user_role: this.user.role,
          entity_id: this.user.entityId,
          project_id: this.user.projectId,
        }),
      });

      if (!res.ok) throw new Error(`Session error: ${res.status}`);
      const data = await res.json() as { token: string };
      this.sessionToken = data.token;

      // Init transport
      this.transport = new Transport({
        apiUrl: this.config.apiUrl,
        token: this.sessionToken,
      });
      this.transport.connect();

    } catch (e) {
      console.warn('[ESGPilot] Failed to acquire session token:', e);
    }
  }

  private async _onFormContextUpdate(ctx: FormContext): Promise<void> {
    if (!this.sessionToken) return;

    try {
      const nudge = await this.transport.post('/v1/forms/context', {
        form_id: ctx.formId,
        framework: ctx.framework,
        section: ctx.section,
        fy: ctx.fy,
        entity_id: ctx.entityId,
        project_id: ctx.projectId,
        fields: ctx.fields.map((f) => ({
          field_code: f.fieldCode,
          value: f.value,
          unit: f.unit,
          label: f.label,
        })),
      }) as NudgePayload;

      const section = ctx.section ?? ctx.formId;
      this.nudgeManager.propose(section, nudge);

    } catch (e) {
      console.debug('[ESGPilot] Form context error:', e);
    }
  }

  private _mountWidget(): void {
    if (typeof document === 'undefined') return;

    // Create host element + Shadow DOM
    const host = document.createElement('div');
    host.id = 'esgpilot-widget-host';
    host.setAttribute('aria-label', 'ESGPilot ESG Copilot');

    // Base styles on host (outside Shadow DOM for positioning)
    Object.assign(host.style, {
      position: 'fixed',
      bottom: '24px',
      right: this.config.position === 'bottom-right' ? '24px' : 'auto',
      left: this.config.position === 'bottom-left' ? '24px' : 'auto',
      zIndex: '2147483647',  // Max z-index
      fontFamily: 'sans-serif',
    });

    document.body.appendChild(host);
    this.widgetRoot = host.attachShadow({ mode: 'open' });

    this._renderFab();
  }

  private _renderFab(): void {
    if (!this.widgetRoot) return;

    const primaryColor = this.config.theme.primaryColor ?? '#1a7a4a';

    this.widgetRoot.innerHTML = `
      <style>
        :host { display: block; }
        .fab {
          width: 56px; height: 56px;
          border-radius: 50%;
          background: ${primaryColor};
          border: none; cursor: pointer;
          box-shadow: 0 4px 16px rgba(0,0,0,0.18);
          display: flex; align-items: center; justify-content: center;
          transition: transform 0.15s ease, box-shadow 0.15s ease;
          outline: none;
        }
        .fab:hover { transform: scale(1.07); box-shadow: 0 6px 20px rgba(0,0,0,0.22); }
        .fab:focus-visible { outline: 3px solid ${primaryColor}; outline-offset: 3px; }
        .fab svg { width: 28px; height: 28px; fill: #fff; }
        .pulse::after {
          content: '';
          position: absolute;
          width: 12px; height: 12px;
          background: #f59e0b;
          border-radius: 50%;
          top: 2px; right: 2px;
          border: 2px solid #fff;
        }
        .fab-wrap { position: relative; display: inline-block; }
      </style>
      <div class="fab-wrap">
        <button
          class="fab"
          aria-label="Open ESGPilot copilot"
          title="ESGPilot — ESG Reporting Copilot"
          id="esgpilot-fab"
        >
          <!-- Leaf/ESG icon -->
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22l1-2.3A4.49 4.49 0 0 0 8 20C19 20 22 3 22 3c-1 2-8 2-8 2s.96 8-8.08 10.66L7 15"/>
          </svg>
        </button>
      </div>
    `;

    this.widgetRoot.getElementById('esgpilot-fab')?.addEventListener('click', () => {
      this.openPanel();
    });
  }

  private _showNudge(payload: NudgePayload): void {
    if (!this.widgetRoot) return;

    const severityColors: Record<string, string> = {
      critical: '#dc2626',
      warn: '#d97706',
      info: '#2563eb',
    };

    const color = severityColors[payload.topSeverity] ?? '#2563eb';
    const primaryColor = this.config.theme.primaryColor ?? '#1a7a4a';

    // Add nudge card above FAB
    const existingNudge = this.widgetRoot.getElementById('esgpilot-nudge');
    if (existingNudge) existingNudge.remove();

    const nudgeEl = document.createElement('div');
    nudgeEl.id = 'esgpilot-nudge';
    nudgeEl.setAttribute('role', 'dialog');
    nudgeEl.setAttribute('aria-label', 'ESGPilot suggestions available');
    nudgeEl.innerHTML = `
      <style>
        .nudge-card {
          background: #fff;
          border: 1px solid #e5e7eb;
          border-left: 4px solid ${color};
          border-radius: 10px;
          padding: 12px 14px;
          box-shadow: 0 4px 20px rgba(0,0,0,0.12);
          margin-bottom: 10px;
          min-width: 240px; max-width: 300px;
          font-family: system-ui, -apple-system, sans-serif;
          font-size: 13px;
          line-height: 1.45;
          color: #111827;
          animation: slideUp 0.2s ease;
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .nudge-title { font-weight: 600; margin-bottom: 4px; }
        .nudge-subtitle { color: #6b7280; font-size: 12px; margin-bottom: 10px; }
        .nudge-actions { display: flex; gap: 8px; }
        .btn-yes {
          flex: 1; padding: 6px 10px;
          background: ${primaryColor}; color: #fff;
          border: none; border-radius: 6px;
          cursor: pointer; font-size: 12px; font-weight: 600;
        }
        .btn-yes:hover { opacity: 0.9; }
        .btn-later {
          flex: 1; padding: 6px 10px;
          background: #f3f4f6; color: #374151;
          border: 1px solid #d1d5db; border-radius: 6px;
          cursor: pointer; font-size: 12px;
        }
        .btn-later:hover { background: #e5e7eb; }
        .btn-mute {
          background: none; border: none;
          color: #9ca3af; font-size: 11px; cursor: pointer;
          padding: 2px 0; margin-top: 6px; width: 100%; text-align: right;
        }
      </style>
      <div class="nudge-card">
        <div class="nudge-title">💡 Want to explore some suggestions?</div>
        <div class="nudge-subtitle">${payload.count} issue${payload.count !== 1 ? 's' : ''} found · ${payload.topSeverity}</div>
        <div class="nudge-actions">
          <button class="btn-yes" id="nudge-yes">Yes, show me</button>
          <button class="btn-later" id="nudge-later">Later</button>
        </div>
        <button class="btn-mute" id="nudge-mute">Mute for this session</button>
      </div>
    `;

    this.widgetRoot.querySelector('.fab-wrap')?.before(nudgeEl);

    this.widgetRoot.getElementById('nudge-yes')?.addEventListener('click', () => {
      nudgeEl.remove();
      this.openPanel();
    });
    this.widgetRoot.getElementById('nudge-later')?.addEventListener('click', () => {
      nudgeEl.remove();
      this.nudgeManager.dismiss();
      this._emit({ type: 'nudge_dismissed' });
    });
    this.widgetRoot.getElementById('nudge-mute')?.addEventListener('click', () => {
      nudgeEl.remove();
      this.nudgeManager.muteSession();
      this._emit({ type: 'nudge_dismissed' });
    });

    this._emit({ type: 'nudge_shown', count: payload.count, severity: payload.topSeverity });
  }

  private _dismissNudge(): void {
    this.widgetRoot?.getElementById('esgpilot-nudge')?.remove();
  }

  private _renderPanel(open: boolean): void {
    if (!this.widgetRoot) return;

    const existing = this.widgetRoot.getElementById('esgpilot-panel');

    if (!open) {
      existing?.remove();
      this._removeOverlay();
      return;
    }

    if (existing) return;

    // Inject backdrop blur overlay into the host document
    this._injectOverlay();

    // Lazy-load the panel web component
    import('../components/ChatPanel').then(({ ChatPanel }) => {
      if (!customElements.get('esgpilot-panel')) {
        customElements.define('esgpilot-panel', ChatPanel);
      }

      const panel = document.createElement('esgpilot-panel') as HTMLElement & {
        token?: string; apiUrl?: string; lang?: string; theme?: unknown;
      };
      panel.id = 'esgpilot-panel';
      if (this.sessionToken) panel.token = this.sessionToken;
      panel.apiUrl = this.config.apiUrl;
      panel.lang = this.config.lang;
      panel.theme = this.config.theme;

      panel.addEventListener('close', () => this.closePanel());
      panel.addEventListener('jump-to-field', (e: Event) => {
        const detail = (e as CustomEvent<{ fieldCode: string }>).detail;
        this._jumpToField(detail.fieldCode);
      });

      this.widgetRoot!.appendChild(panel);
    });
  }

  private _injectOverlay(): void {
    if (document.getElementById('esgpilot-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'esgpilot-overlay';
    Object.assign(overlay.style, {
      position: 'fixed',
      inset: '0',
      zIndex: '2147483640',
      backdropFilter: 'blur(8px) saturate(0.9)',
      background: 'rgba(10, 10, 10, 0.35)',
      transition: 'opacity 0.15s',
    });
    overlay.addEventListener('click', () => this.closePanel());
    document.body.appendChild(overlay);
  }

  private _removeOverlay(): void {
    document.getElementById('esgpilot-overlay')?.remove();
  }

  private _jumpToField(fieldCode: string): void {
    const el =
      document.querySelector(`[data-esg-field="${fieldCode}"]`) ??
      document.querySelector(`[name="${fieldCode}"]`) ??
      document.getElementById(fieldCode);

    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      if (el instanceof HTMLElement) {
        el.focus();
        el.style.outline = '3px solid #f59e0b';
        setTimeout(() => {
          (el as HTMLElement).style.outline = '';
        }, 2500);
      }
      this.closePanel();
      this._emit({ type: 'field_jumped', fieldCode });
    }
  }

  private _emit(event: SDKEvent): void {
    this.listeners.forEach((l) => {
      try { l(event); } catch { /* ignore listener errors */ }
    });
    window.dispatchEvent(new CustomEvent('esgpilot', { detail: event }));
  }
}

// Export singleton accessors
export const ESGPilotSDK = ESGPilotSDKClass.getInstance();
export type { ESGPilotSDKClass };
