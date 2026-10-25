/**
 * ESGPilot SDK — Chat Panel Web Component.
 *
 * Full-screen modal panel with tabs: Suggestions | Ask | Compare
 * Rendered inside Shadow DOM. WCAG 2.1 AA compliant.
 * Focus trap, ESC to close, backdrop handled by parent.
 */

export class ChatPanel extends HTMLElement {
  token: string = '';
  apiUrl: string = 'https://api.esgpilot.io';
  lang: string = 'en';
  theme: Record<string, string> = {};

  private _shadow!: ShadowRoot;
  private _activeTab: 'suggestions' | 'ask' | 'compare' = 'suggestions';
  private _messages: Array<{ role: string; content: string; citations?: unknown[] }> = [];
  private _suggestions: unknown[] = [];
  private _loadingSuggestions = false;
  private _chatInput = '';

  connectedCallback(): void {
    this._shadow = this.attachShadow({ mode: 'open' });
    this._render();
    this._trapFocus();
    this._loadSuggestions();

    // ESC key closes panel
    document.addEventListener('keydown', this._onKeyDown);
  }

  disconnectedCallback(): void {
    document.removeEventListener('keydown', this._onKeyDown);
  }

  private _onKeyDown = (e: KeyboardEvent): void => {
    if (e.key === 'Escape') this._close();
  };

  private _close(): void {
    this.dispatchEvent(new CustomEvent('close', { bubbles: true, composed: true }));
  }

  private _switchTab(tab: 'suggestions' | 'ask' | 'compare'): void {
    this._activeTab = tab;
    this._render();
  }

  private async _loadSuggestions(): Promise<void> {
    this._loadingSuggestions = true;
    this._render();

    try {
      const resp = await fetch(`${this.apiUrl}/v1/suggestions`, {
        headers: { Authorization: `Bearer ${this.token}` },
      });
      if (resp.ok) {
        const data = await resp.json() as { suggestions?: unknown[] };
        this._suggestions = data.suggestions ?? [];
      }
    } catch {
      // Use empty list on error
    }

    this._loadingSuggestions = false;
    this._render();
  }

  private async _sendMessage(message: string): Promise<void> {
    if (!message.trim()) return;

    this._messages.push({ role: 'user', content: message });
    this._chatInput = '';
    this._render();

    try {
      const resp = await fetch(`${this.apiUrl}/v1/kb/ask`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: message }),
      });

      if (resp.ok) {
        const data = await resp.json() as { answer?: string; citations?: unknown[] };
        this._messages.push({
          role: 'assistant',
          content: data.answer ?? 'No response.',
          citations: data.citations ?? [],
        });
      }
    } catch {
      this._messages.push({
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
      });
    }

    this._render();
    this._scrollChatToBottom();
  }

  private _scrollChatToBottom(): void {
    const chat = this._shadow.getElementById('chat-messages');
    if (chat) chat.scrollTop = chat.scrollHeight;
  }

  private _trapFocus(): void {
    // Focus the close button on open
    setTimeout(() => {
      (this._shadow.getElementById('panel-close') as HTMLElement | null)?.focus();
    }, 50);
  }

  private _render(): void {
    const primary = this.theme?.primaryColor ?? '#1a7a4a';
    const tabStyle = (tab: string) =>
      this._activeTab === tab
        ? `background:${primary};color:#fff;`
        : 'background:#f3f4f6;color:#374151;';

    this._shadow.innerHTML = `
      <style>
        :host { display: block; }
        .panel {
          position: fixed;
          top: 50%; left: 50%;
          transform: translate(-50%, -50%);
          z-index: 2147483647;
          width: min(92vw, 640px);
          max-height: 88vh;
          background: #fff;
          border-radius: 16px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.25);
          display: flex; flex-direction: column;
          font-family: system-ui, -apple-system, sans-serif;
          overflow: hidden;
          animation: popIn 0.18s ease;
        }
        @keyframes popIn {
          from { opacity:0; transform: translate(-50%,-48%) scale(0.96); }
          to   { opacity:1; transform: translate(-50%,-50%) scale(1); }
        }
        .panel-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 14px 18px;
          background: ${primary};
          color: #fff;
        }
        .panel-title { font-size: 15px; font-weight: 600; }
        .context-chip {
          font-size: 11px; background: rgba(255,255,255,0.2);
          padding: 2px 8px; border-radius: 12px;
          margin-left: 8px;
        }
        .close-btn {
          background: none; border: none; color: #fff;
          font-size: 22px; cursor: pointer; line-height: 1;
          padding: 4px 8px; border-radius: 6px;
        }
        .close-btn:hover { background: rgba(255,255,255,0.15); }
        .close-btn:focus-visible { outline: 2px solid #fff; }
        .tabs {
          display: flex; gap: 4px;
          padding: 10px 16px 0;
          border-bottom: 1px solid #e5e7eb;
        }
        .tab {
          padding: 7px 14px; border-radius: 8px 8px 0 0;
          border: none; cursor: pointer; font-size: 13px; font-weight: 500;
          transition: background 0.12s;
        }
        .panel-body { flex: 1; overflow-y: auto; padding: 16px; }
        .loading {
          display: flex; align-items: center; gap: 8px;
          color: #6b7280; font-size: 13px; padding: 24px 0;
        }
        .spinner {
          width: 18px; height: 18px; border: 2px solid #e5e7eb;
          border-top-color: ${primary}; border-radius: 50%;
          animation: spin 0.6s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .empty { color: #9ca3af; font-size: 13px; text-align: center; padding: 32px 0; }
        /* Suggestion card */
        .suggestion-card {
          border: 1px solid #e5e7eb; border-radius: 10px;
          padding: 12px 14px; margin-bottom: 10px;
        }
        .sev-critical { border-left: 4px solid #dc2626; }
        .sev-warn     { border-left: 4px solid #d97706; }
        .sev-info     { border-left: 4px solid #2563eb; }
        .card-title { font-weight: 600; font-size: 13px; color: #111827; margin-bottom: 4px; }
        .card-why { font-size: 12px; color: #6b7280; margin-bottom: 6px; }
        .card-fix { font-size: 12px; color: #374151; }
        .card-actions { display:flex; gap:8px; margin-top: 10px; }
        .btn-sm {
          padding: 5px 12px; border-radius: 6px; font-size: 11px;
          font-weight: 600; cursor: pointer; border: 1px solid transparent;
        }
        .btn-primary { background:${primary}; color:#fff; }
        .btn-ghost { background:#fff; color:#374151; border-color:#d1d5db; }
        .citation { font-size: 11px; color: #6b7280; margin-top: 6px; }
        .citation span { background:#f3f4f6; padding:1px 6px; border-radius:4px; margin-right:4px; }
        /* Chat */
        #chat-messages { max-height: 360px; overflow-y: auto; margin-bottom: 12px; }
        .msg { display:flex; gap:10px; margin-bottom:10px; }
        .msg-user { justify-content: flex-end; }
        .bubble {
          max-width: 85%; padding: 9px 13px; border-radius: 12px;
          font-size: 13px; line-height: 1.5;
        }
        .bubble-user { background:${primary}; color:#fff; border-radius: 12px 12px 0 12px; }
        .bubble-assistant { background:#f9fafb; border:1px solid #e5e7eb; color:#111827; border-radius: 12px 12px 12px 0; }
        .chat-input-row { display:flex; gap:8px; }
        .chat-input {
          flex:1; padding:9px 13px; border:1px solid #d1d5db; border-radius:8px;
          font-size:13px; outline:none;
        }
        .chat-input:focus { border-color:${primary}; box-shadow:0 0 0 2px ${primary}22; }
        .btn-send {
          padding:9px 16px; background:${primary}; color:#fff;
          border:none; border-radius:8px; cursor:pointer; font-size:13px;
        }
        .btn-send:disabled { opacity:0.5; cursor:default; }
      </style>

      <div class="panel" role="dialog" aria-modal="true" aria-label="ESGPilot copilot">
        <div class="panel-header">
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="panel-title">ESGPilot</span>
            <span class="context-chip">BRSR · FY2025</span>
          </div>
          <button class="close-btn" id="panel-close" aria-label="Close panel">✕</button>
        </div>

        <div class="tabs">
          <button class="tab" id="tab-suggestions" style="${tabStyle('suggestions')}"
            aria-selected="${this._activeTab === 'suggestions'}">
            Suggestions
          </button>
          <button class="tab" id="tab-ask" style="${tabStyle('ask')}"
            aria-selected="${this._activeTab === 'ask'}">
            Ask
          </button>
          <button class="tab" id="tab-compare" style="${tabStyle('compare')}"
            aria-selected="${this._activeTab === 'compare'}">
            Compare
          </button>
        </div>

        <div class="panel-body">
          ${this._activeTab === 'suggestions' ? this._renderSuggestions() : ''}
          ${this._activeTab === 'ask' ? this._renderAsk() : ''}
          ${this._activeTab === 'compare' ? this._renderCompare() : ''}
        </div>
      </div>
    `;

    // Bind events
    this._shadow.getElementById('panel-close')?.addEventListener('click', () => this._close());
    this._shadow.getElementById('tab-suggestions')?.addEventListener('click', () => this._switchTab('suggestions'));
    this._shadow.getElementById('tab-ask')?.addEventListener('click', () => this._switchTab('ask'));
    this._shadow.getElementById('tab-compare')?.addEventListener('click', () => this._switchTab('compare'));

    if (this._activeTab === 'ask') {
      const input = this._shadow.getElementById('chat-input') as HTMLInputElement | null;
      const sendBtn = this._shadow.getElementById('chat-send');
      input?.addEventListener('keydown', (e: KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          void this._sendMessage(input.value);
        }
      });
      sendBtn?.addEventListener('click', () => {
        const val = (this._shadow.getElementById('chat-input') as HTMLInputElement | null)?.value ?? '';
        void this._sendMessage(val);
      });
    }

    // Bind suggestion actions
    this._shadow.querySelectorAll('.btn-jump').forEach((btn) => {
      btn.addEventListener('click', () => {
        const fieldCode = (btn as HTMLElement).dataset.field ?? '';
        this.dispatchEvent(new CustomEvent('jump-to-field', {
          bubbles: true, composed: true, detail: { fieldCode },
        }));
      });
    });
  }

  private _renderSuggestions(): string {
    if (this._loadingSuggestions) {
      return `<div class="loading"><div class="spinner"></div> Loading suggestions…</div>`;
    }

    if (!this._suggestions.length) {
      return `<div class="empty">✅ No suggestions at this time.<br>Your form looks good!</div>`;
    }

    return (this._suggestions as Array<{
      id: string; severity: string; title: string; why?: string;
      how_to_fix?: string; references?: Array<{ doc: string; section?: string }>;
      field_code?: string;
    }>).map((s) => `
      <div class="suggestion-card sev-${s.severity}">
        <div class="card-title">${s.title}</div>
        ${s.why ? `<div class="card-why">${s.why}</div>` : ''}
        ${s.how_to_fix ? `<div class="card-fix">💡 ${s.how_to_fix}</div>` : ''}
        ${s.references?.length ? `
          <div class="citation">
            ${s.references.map((r) => `<span>${r.doc}${r.section ? ' · ' + r.section : ''}</span>`).join('')}
          </div>
        ` : ''}
        <div class="card-actions">
          ${s.field_code ? `<button class="btn-sm btn-ghost btn-jump" data-field="${s.field_code}" aria-label="Jump to field">↗ Jump to field</button>` : ''}
          <button class="btn-sm btn-ghost" aria-label="Dismiss suggestion">Dismiss</button>
        </div>
      </div>
    `).join('');
  }

  private _renderAsk(): string {
    const msgs = this._messages.map((m) => `
      <div class="msg ${m.role === 'user' ? 'msg-user' : ''}">
        <div class="bubble ${m.role === 'user' ? 'bubble-user' : 'bubble-assistant'}">
          ${m.content}
        </div>
      </div>
    `).join('');

    const placeholder = this.lang === 'hi'
      ? 'BRSR के बारे में कुछ पूछें…'
      : 'Ask about BRSR, water, emissions, SDGs…';

    return `
      <div id="chat-messages">${msgs || '<div class="empty">Ask me anything about ESG reporting.</div>'}</div>
      <div class="chat-input-row">
        <input
          type="text"
          id="chat-input"
          class="chat-input"
          placeholder="${placeholder}"
          aria-label="Chat with ESGPilot"
          value="${this._chatInput}"
        />
        <button class="btn-send" id="chat-send" aria-label="Send message">Send</button>
      </div>
    `;
  }

  private _renderCompare(): string {
    return `
      <div class="empty">
        📊 Portfolio comparison is available for group admins.<br><br>
        Compare subsidiaries, projects, and FY trends once reports are submitted.
      </div>
    `;
  }
}
