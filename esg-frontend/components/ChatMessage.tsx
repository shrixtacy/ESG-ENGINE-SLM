"use client";

import { Leaf, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { Citation } from "@/lib/api";
import { formatTime } from "@/lib/utils";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  sdgTags?: string[];
  confidence?: number;
  abstained?: boolean;
  timestamp: Date;
  isStreaming?: boolean;
}

function CitationChips({ citations }: { citations: Citation[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!citations.length) return null;

  const visible = expanded ? citations : citations.slice(0, 3);

  return (
    <div className="mt-3 space-y-1">
      <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
        Sources
      </div>
      <div className="flex flex-wrap gap-1.5">
        {visible.map((c, i) => (
          <a
            key={i}
            href={c.url || "#"}
            target={c.url ? "_blank" : undefined}
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-green-50 border border-green-100 text-[11px] text-green-700 hover:bg-green-100 transition-colors max-w-[260px]"
            title={c.excerpt}
          >
            <span className="truncate">{c.doc_title}</span>
            {c.section && <span className="text-green-400 shrink-0">· {c.section}</span>}
            {c.url && <ExternalLink className="w-2.5 h-2.5 shrink-0 text-green-400" />}
          </a>
        ))}
      </div>
      {citations.length > 3 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600 mt-1"
        >
          {expanded ? (
            <><ChevronUp className="w-3 h-3" /> Show less</>
          ) : (
            <><ChevronDown className="w-3 h-3" /> +{citations.length - 3} more sources</>
          )}
        </button>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      <span className="w-2 h-2 rounded-full bg-green-400 dot-1" />
      <span className="w-2 h-2 rounded-full bg-green-400 dot-2" />
      <span className="w-2 h-2 rounded-full bg-green-400 dot-3" />
    </div>
  );
}

export default function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";

  if (isUser) {
    return (
      <div className="msg-animate flex justify-end mb-4">
        <div className="max-w-[75%]">
          <div className="bg-green-700 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-sm">
            {msg.content}
          </div>
          <div className="text-[10px] text-gray-400 text-right mt-1 pr-1">
            {formatTime(msg.timestamp)}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="msg-animate flex gap-3 mb-5">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-xl bg-green-50 border border-green-100 flex items-center justify-center shrink-0 mt-0.5">
        <Leaf className="w-4 h-4 text-green-600" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-gray-700">ESG AI Engine</span>
          {msg.confidence !== undefined && msg.confidence > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-50 text-green-600 border border-green-100">
              {(msg.confidence * 100).toFixed(0)}% confident
            </span>
          )}
          {msg.abstained && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-100">
              Abstained
            </span>
          )}
        </div>

        <div className="bg-white rounded-2xl rounded-tl-sm border border-gray-100 px-4 py-3 shadow-sm">
          {msg.isStreaming && !msg.content ? (
            <TypingIndicator />
          ) : (
            <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {msg.content}
              {msg.isStreaming && (
                <span className="inline-block w-0.5 h-4 bg-green-500 ml-0.5 animate-pulse align-text-bottom" />
              )}
            </div>
          )}

          {!msg.isStreaming && msg.citations && msg.citations.length > 0 && (
            <CitationChips citations={msg.citations} />
          )}

          {msg.sdgTags && msg.sdgTags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {msg.sdgTags.map((tag) => (
                <span key={tag} className="px-2 py-0.5 rounded-full bg-blue-50 border border-blue-100 text-[11px] text-blue-600 font-medium">
                  SDG {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="text-[10px] text-gray-400 mt-1 pl-1">
          {formatTime(msg.timestamp)}
        </div>
      </div>
    </div>
  );
}
