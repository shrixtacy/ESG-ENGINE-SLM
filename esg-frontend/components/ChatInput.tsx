"use client";

import { Paperclip, SendHorizonal, Loader2 } from "lucide-react";
import { useRef, useState, KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  loading: boolean;
  disabled?: boolean;
}

export default function ChatInput({ onSend, loading, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const msg = value.trim();
    if (!msg || loading) return;
    onSend(msg);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }

  const canSend = value.trim().length > 0 && !loading && !disabled;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-[#fafaf8] via-[#fafaf8]/95 to-transparent pt-6 pb-5 px-4">
      <div className="max-w-2xl mx-auto">
        <div
          className={cn(
            "flex items-end gap-2 bg-white rounded-2xl border shadow-md px-3 py-2.5 transition-all",
            disabled ? "border-gray-200 opacity-60" : "border-gray-200 focus-within:border-green-300 focus-within:shadow-green-100"
          )}
        >
          {/* Attachment */}
          <button
            className="p-1.5 rounded-xl text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors shrink-0 mb-0.5"
            aria-label="Attach file"
            disabled={disabled}
          >
            <Paperclip className="w-4 h-4" />
          </button>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder="Ask anything about your ESG reports, compliance, metrics…"
            rows={1}
            disabled={disabled || loading}
            className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none py-1 max-h-40 leading-relaxed"
          />

          {/* Send */}
          <button
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Send message"
            className={cn(
              "p-2 rounded-xl shrink-0 mb-0.5 transition-all",
              canSend
                ? "bg-green-700 text-white hover:bg-green-800 shadow-sm"
                : "bg-gray-100 text-gray-300 cursor-not-allowed"
            )}
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <SendHorizonal className="w-4 h-4" />
            )}
          </button>
        </div>

        <p className="text-center text-[10px] text-gray-400 mt-2">
          ESG AI Engine may make mistakes. Verify important data against official BRSR/SEBI sources.
        </p>
      </div>
    </div>
  );
}
