"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { MessageSquare, Lightbulb, X, RefreshCw } from "lucide-react";
import TopNav from "@/components/TopNav";
import EmptyState from "@/components/EmptyState";
import ChatMessage, { Message } from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import SuggestionsPanel from "@/components/SuggestionsPanel";
import {
  createDemoSession,
  askQuestion,
  getSuggestions,
  checkHealth,
  SuggestionCard,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Tab = "chat" | "suggestions";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState<string>("");
  const tokenRef = useRef<string>("");
  const [apiStatus, setApiStatus] = useState<"online" | "offline" | "checking">("checking");
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [suggestions, setSuggestions] = useState<SuggestionCard[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Init: session + health check ─────────────────────────
  useEffect(() => {
    async function init() {
      const status = await checkHealth();
      setApiStatus(status);

      const t = await createDemoSession();
      setToken(t);
      // Store in ref so handleSend can always read the latest value
      tokenRef.current = t;

      if (status === "online") {
        setLoadingSuggestions(true);
        const s = await getSuggestions(t);
        setSuggestions(s);
        setLoadingSuggestions(false);
      }
    }
    init();
  }, []);

  // ── Auto-scroll ───────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Send message ──────────────────────────────────────────
  const handleSend = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      // Always use the latest token from ref (avoids stale closure)
      const currentToken = tokenRef.current || token;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setLoading(true);

      try {
        const answer = await askQuestion(text, currentToken);

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? {
                  ...m,
                  content: answer.answer,
                  citations: answer.citations,
                  confidence: answer.confidence,
                  abstained: answer.abstained,
                  isStreaming: false,
                }
              : m
          )
        );
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? {
                  ...m,
                  content: "Sorry, something went wrong. Please check that the API server is running.",
                  isStreaming: false,
                }
              : m
          )
        );
      } finally {
        setLoading(false);
      }
    },
    [loading, token]
  );

  // ── Clear chat ────────────────────────────────────────────
  function clearChat() {
    setMessages([]);
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="min-h-screen bg-blob-green bg-[#fafaf8] flex flex-col">
      <TopNav apiStatus={apiStatus} />

      {/* Tab bar (only when chat has messages) */}
      {!isEmpty && (
        <div className="fixed top-14 left-0 right-0 z-40 bg-white/80 backdrop-blur-md border-b border-gray-100">
          <div className="max-w-2xl mx-auto px-4 flex items-center gap-1 h-10">
            <button
              onClick={() => setActiveTab("chat")}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 rounded-lg text-sm font-medium transition-colors",
                activeTab === "chat"
                  ? "bg-green-50 text-green-700"
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Chat
            </button>
            <button
              onClick={() => setActiveTab("suggestions")}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 rounded-lg text-sm font-medium transition-colors",
                activeTab === "suggestions"
                  ? "bg-green-50 text-green-700"
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              <Lightbulb className="w-3.5 h-3.5" />
              Suggestions
              {suggestions.length > 0 && (
                <span className="ml-0.5 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold">
                  {suggestions.length}
                </span>
              )}
            </button>

            {/* Spacer + clear button */}
            <div className="flex-1" />
            <button
              onClick={clearChat}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 px-2 py-1 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              New chat
            </button>
          </div>
        </div>
      )}

      {/* Main content */}
      <main
        className={cn(
          "flex-1 flex flex-col",
          isEmpty ? "pt-14" : "pt-24",
          "pb-0"
        )}
      >
        {isEmpty ? (
          <EmptyState onPrompt={handleSend} />
        ) : (
          <div className="flex-1 overflow-y-auto pb-36 pt-4">
            <div className="max-w-2xl mx-auto px-4">
              {activeTab === "chat" && (
                <>
                  {messages.map((msg) => (
                    <ChatMessage key={msg.id} msg={msg} />
                  ))}
                  <div ref={messagesEndRef} />
                </>
              )}

              {activeTab === "suggestions" && (
                <SuggestionsPanel
                  suggestions={suggestions}
                  loading={loadingSuggestions}
                />
              )}
            </div>
          </div>
        )}
      </main>

      <ChatInput onSend={handleSend} loading={loading} />

      {/* API offline banner */}
      {apiStatus === "offline" && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 rounded-full text-xs text-amber-700 shadow-md">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          API offline — running in demo mode. Start the FastAPI server on port 8080.
        </div>
      )}
    </div>
  );
}
