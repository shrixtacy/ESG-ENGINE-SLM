"use client";

import { AlertCircle, AlertTriangle, Info, ExternalLink, Loader2 } from "lucide-react";
import { SuggestionCard } from "@/lib/api";
import { cn } from "@/lib/utils";

const SEV_CONFIG = {
  critical: {
    icon: AlertCircle,
    bg: "bg-red-50",
    border: "border-red-200",
    badge: "bg-red-100 text-red-700",
    bar: "bg-red-500",
    text: "text-red-700",
  },
  warn: {
    icon: AlertTriangle,
    bg: "bg-amber-50",
    border: "border-amber-200",
    badge: "bg-amber-100 text-amber-700",
    bar: "bg-amber-500",
    text: "text-amber-700",
  },
  info: {
    icon: Info,
    bg: "bg-blue-50",
    border: "border-blue-200",
    badge: "bg-blue-100 text-blue-700",
    bar: "bg-blue-400",
    text: "text-blue-700",
  },
};

function SuggestionCardItem({ card }: { card: SuggestionCard }) {
  const sev = SEV_CONFIG[card.severity] || SEV_CONFIG.info;
  const Icon = sev.icon;

  return (
    <div className={cn("rounded-xl border p-4 mb-3", sev.bg, sev.border)}>
      <div className="flex items-start gap-2.5 mb-2">
        <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", sev.text)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-semibold text-gray-800 leading-snug">{card.title}</span>
            <span className={cn("text-[10px] px-1.5 py-0.5 rounded-full font-medium", sev.badge)}>
              {card.severity}
            </span>
          </div>
          {card.why && (
            <p className="text-xs text-gray-600 leading-relaxed mb-2">{card.why}</p>
          )}
          {card.how_to_fix && (
            <div className="bg-white/70 rounded-lg px-3 py-2 border border-white mb-2">
              <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-0.5">How to fix</div>
              <p className="text-xs text-gray-700 leading-relaxed">{card.how_to_fix}</p>
            </div>
          )}
          {card.references.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {card.references.map((r, i) => (
                <span key={i} className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-white/80 border border-gray-200 text-gray-500">
                  {r.doc}{r.section ? ` · ${r.section}` : ""}
                </span>
              ))}
            </div>
          )}
          {card.sdg_tags.length > 0 && (
            <div className="flex gap-1 mt-2">
              {card.sdg_tags.map((tag) => (
                <span key={tag} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 border border-blue-100 text-blue-600 font-medium">
                  SDG {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface SuggestionsPanelProps {
  suggestions: SuggestionCard[];
  loading: boolean;
}

export default function SuggestionsPanel({ suggestions, loading }: SuggestionsPanelProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 gap-2 text-gray-400">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-sm">Loading suggestions…</span>
      </div>
    );
  }

  if (!suggestions.length) {
    return (
      <div className="text-center py-16">
        <div className="text-3xl mb-3">✅</div>
        <div className="text-sm font-medium text-gray-600">No issues found</div>
        <div className="text-xs text-gray-400 mt-1">Your form looks good!</div>
      </div>
    );
  }

  const critical = suggestions.filter((s) => s.severity === "critical").length;
  const warn = suggestions.filter((s) => s.severity === "warn").length;
  const info = suggestions.filter((s) => s.severity === "info").length;

  return (
    <div>
      {/* Summary row */}
      <div className="flex gap-3 mb-4 p-3 bg-gray-50 rounded-xl border border-gray-100">
        {critical > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-red-600 font-medium">
            <AlertCircle className="w-3.5 h-3.5" />
            {critical} critical
          </div>
        )}
        {warn > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-amber-600 font-medium">
            <AlertTriangle className="w-3.5 h-3.5" />
            {warn} warnings
          </div>
        )}
        {info > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-blue-600 font-medium">
            <Info className="w-3.5 h-3.5" />
            {info} info
          </div>
        )}
      </div>

      {suggestions.map((s) => (
        <SuggestionCardItem key={s.id} card={s} />
      ))}
    </div>
  );
}
