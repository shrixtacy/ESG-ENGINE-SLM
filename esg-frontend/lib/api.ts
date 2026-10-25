// ESGPilot API client — hits the FastAPI backend
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export interface Citation {
  doc_title: string;
  section?: string;
  version?: string;
  url?: string;
  excerpt?: string;
}

export interface KBAnswer {
  answer: string;
  citations: Citation[];
  confidence: number;
  abstained: boolean;
}

export interface SuggestionCard {
  id: string;
  scope: string;
  severity: "info" | "warn" | "critical";
  title: string;
  why?: string;
  how_to_fix?: string;
  references: { doc: string; section?: string; version?: string }[];
  sdg_tags: string[];
  confidence: number;
  source: string;
  field_code?: string;
}

export interface NudgeResponse {
  has_findings: boolean;
  count: number;
  top_severity: string;
  summary?: string;
}

// ──────────────────────────────────────────────
// Session
// ──────────────────────────────────────────────

export async function createDemoSession(): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/v1/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant_key: "demo_key",
        user_id: "demo_user",
        user_role: "project_user",
      }),
      signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) return "demo_token_offline";
    const data = await res.json();
    return data.token as string;
  } catch {
    // Backend offline — run in demo mode
    return "demo_token_offline";
  }
}

// ──────────────────────────────────────────────
// Knowledge Q&A
// ──────────────────────────────────────────────

export async function askQuestion(
  question: string,
  token: string,
  framework?: string
): Promise<KBAnswer> {
  const res = await fetch(`${API_BASE}/v1/kb/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question, framework: framework || "BRSR" }),
  });

  if (!res.ok) {
    // Offline fallback for testing
    return {
      answer: `[Demo mode — API offline]\n\nYou asked: "${question}"\n\nOnce the FastAPI backend is running on port 8080, real answers with citations will appear here.`,
      citations: [],
      confidence: 0,
      abstained: false,
    };
  }
  return res.json();
}

// ──────────────────────────────────────────────
// Suggestions
// ──────────────────────────────────────────────

export async function getSuggestions(token: string): Promise<SuggestionCard[]> {
  try {
    const res = await fetch(`${API_BASE}/v1/suggestions`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.suggestions as SuggestionCard[]) || [];
  } catch {
    return [];
  }
}

// ──────────────────────────────────────────────
// SDG Mapping
// ──────────────────────────────────────────────

export async function mapToSDG(text: string, token: string) {
  const res = await fetch(`${API_BASE}/v1/sdg/map`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) return { tags: [] };
  return res.json();
}

// ──────────────────────────────────────────────
// Health check
// ──────────────────────────────────────────────

export async function checkHealth(): Promise<"online" | "offline"> {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok ? "online" : "offline";
  } catch {
    return "offline";
  }
}
