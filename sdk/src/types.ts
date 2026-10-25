/**
 * ESGPilot SDK — TypeScript type definitions.
 */

export interface SDKConfig {
  /** Tenant identifier */
  tenant: string;
  /** Public API key */
  key: string;
  /** API base URL */
  apiUrl?: string;
  /** Widget position */
  position?: 'bottom-right' | 'bottom-left';
  /** UI language */
  lang?: 'en' | 'hi';
  /** Theming overrides */
  theme?: ThemeConfig;
}

export interface ThemeConfig {
  primaryColor?: string;    // e.g. "#1a7a4a"
  accentColor?: string;
  fontFamily?: string;
  borderRadius?: string;    // e.g. "8px"
  logoUrl?: string;
}

export interface UserContext {
  id: string;
  role: 'project_user' | 'entity_admin' | 'group_admin' | 'auditor' | 'tenant_admin';
  entityId?: string;
  projectId?: string;
  name?: string;
}

export interface FormConfig {
  /** Framework identifier */
  framework: 'BRSR' | 'GRI' | 'SDG' | 'CSR';
  /** Section code, e.g. 'C-P6' */
  section?: string;
  /** Financial year, e.g. 'FY2025' */
  fy?: string;
}

export interface FieldData {
  fieldCode: string;
  value?: string | number | null;
  unit?: string;
  label?: string;
}

export interface FormContext {
  formId: string;
  framework: string;
  section?: string;
  fy: string;
  entityId?: string;
  projectId?: string;
  fields: FieldData[];
}

export interface SuggestionCard {
  id: string;
  scope: 'field' | 'section' | 'form' | 'portfolio';
  severity: 'info' | 'warn' | 'critical';
  title: string;
  why?: string;
  howToFix?: string;
  references: Reference[];
  sdgTags: string[];
  confidence: number;
  source: 'rule' | 'slm' | 'hybrid';
  fieldCode?: string;
}

export interface Reference {
  doc: string;
  section?: string;
  version?: string;
  url?: string;
}

export interface NudgePayload {
  hasFindings: boolean;
  count: number;
  topSeverity: 'info' | 'warn' | 'critical';
  summary?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp?: string;
}

export interface Citation {
  docTitle: string;
  section?: string;
  version?: string;
  url?: string;
  excerpt?: string;
}

export type SDKEvent =
  | { type: 'field_changed'; fieldCode: string; value: unknown }
  | { type: 'section_completed'; section: string }
  | { type: 'nudge_shown'; count: number; severity: string }
  | { type: 'nudge_dismissed' }
  | { type: 'panel_opened' }
  | { type: 'panel_closed' }
  | { type: 'suggestion_accepted'; suggestionId: string }
  | { type: 'suggestion_ignored'; suggestionId: string }
  | { type: 'field_jumped'; fieldCode: string };
