/**
 * ESGPilot SDK — Transport Layer.
 *
 * Manages WebSocket connection with SSE/HTTP fallback.
 * Handles reconnect/backoff, authentication, and message routing.
 */

export interface TransportConfig {
  apiUrl: string;
  token: string;
}

export type MessageHandler = (data: unknown) => void;

export class Transport {
  private ws: WebSocket | null = null;
  private config: TransportConfig;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30_000;
  private reconnectAttempts = 0;
  private intentionalClose = false;

  constructor(config: TransportConfig) {
    this.config = config;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    const wsUrl = this.config.apiUrl
      .replace(/^https/, 'wss')
      .replace(/^http/, 'ws');

    try {
      this.ws = new WebSocket(`${wsUrl}/v1/chat/stream`);

      this.ws.onopen = () => {
        this.reconnectDelay = 1000;
        this.reconnectAttempts = 0;
        this.emit('connected', {});
        // Send auth
        this.send({ type: 'auth', token: this.config.token });
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string);
          const type = (data as { type?: string }).type || 'message';
          this.emit(type, data);
        } catch {
          // Ignore parse errors
        }
      };

      this.ws.onclose = () => {
        if (!this.intentionalClose) {
          this._scheduleReconnect();
        }
        this.emit('disconnected', {});
      };

      this.ws.onerror = () => {
        this.emit('error', { message: 'WebSocket error' });
      };

    } catch {
      this._scheduleReconnect();
    }
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.ws?.close();
    this.ws = null;
  }

  send(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  /** Send via HTTP fallback (for non-streaming requests). */
  async post(path: string, body: unknown): Promise<unknown> {
    const response = await fetch(`${this.config.apiUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.config.token}`,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async get(path: string): Promise<unknown> {
    const response = await fetch(`${this.config.apiUrl}${path}`, {
      headers: { Authorization: `Bearer ${this.config.token}` },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  on(event: string, handler: MessageHandler): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event)!.push(handler);
  }

  off(event: string, handler: MessageHandler): void {
    const list = this.handlers.get(event);
    if (list) {
      const idx = list.indexOf(handler);
      if (idx >= 0) list.splice(idx, 1);
    }
  }

  private emit(event: string, data: unknown): void {
    this.handlers.get(event)?.forEach((h) => h(data));
    this.handlers.get('*')?.forEach((h) => h({ event, data }));
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= 10) return;
    const delay = Math.min(this.reconnectDelay * 2 ** this.reconnectAttempts, this.maxReconnectDelay);
    this.reconnectAttempts++;
    setTimeout(() => this.connect(), delay);
  }

  updateToken(token: string): void {
    this.config.token = token;
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({ type: 'auth', token });
    }
  }
}
