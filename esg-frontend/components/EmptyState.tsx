"use client";

import { BarChart2, FileText, Leaf, TrendingUp } from "lucide-react";

interface PromptChip {
  icon: React.ReactNode;
  action: string;
  detail: string;
  prompt: string;
}

const CHIPS: PromptChip[] = [
  {
    icon: <FileText className="w-5 h-5 text-green-600" />,
    action: "Summarize",
    detail: "my latest ESG report",
    prompt: "Summarize the key findings from a BRSR ESG report. What are the most important sections?",
  },
  {
    icon: <BarChart2 className="w-5 h-5 text-green-600" />,
    action: "Suggest ways",
    detail: "to improve ESG score",
    prompt: "What are the most impactful ways to improve our BRSR readiness score?",
  },
  {
    icon: <Leaf className="w-5 h-5 text-green-600" />,
    action: "Explain",
    detail: "SEBI BRSR requirement",
    prompt: "Explain the SEBI BRSR disclosure requirement — who must comply and from when?",
  },
  {
    icon: <TrendingUp className="w-5 h-5 text-green-600" />,
    action: "Compare",
    detail: "with industry benchmarks",
    prompt: "How do I compare our Scope 1 GHG emissions with industry benchmarks in BRSR?",
  },
];

interface EmptyStateProps {
  onPrompt: (text: string) => void;
}

export default function EmptyState({ onPrompt }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4 pb-32 pt-20">
      {/* Icon */}
      <div className="w-16 h-16 rounded-2xl bg-green-50 border border-green-100 flex items-center justify-center mb-6 shadow-sm">
        <Leaf className="w-8 h-8 text-green-600" />
      </div>

      {/* Title */}
      <h1 className="text-4xl font-bold text-gray-900 mb-3 tracking-tight">
        ESG <span className="text-green-600">AI Engine</span>
      </h1>
      <p className="text-gray-500 text-center max-w-sm leading-relaxed mb-10">
        Ask anything about your ESG reports, compliance, metrics
        <br />or get actionable suggestions.
      </p>

      {/* Prompt chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full max-w-2xl">
        {CHIPS.map((chip) => (
          <button
            key={chip.action}
            onClick={() => onPrompt(chip.prompt)}
            className="group flex flex-col gap-2 p-4 bg-white rounded-2xl border border-gray-200 hover:border-green-300 hover:shadow-sm transition-all text-left"
          >
            <div className="w-9 h-9 rounded-xl bg-green-50 flex items-center justify-center group-hover:bg-green-100 transition-colors">
              {chip.icon}
            </div>
            <div>
              <div className="text-sm font-semibold text-gray-800">{chip.action}</div>
              <div className="text-xs text-gray-400 leading-snug">{chip.detail}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
