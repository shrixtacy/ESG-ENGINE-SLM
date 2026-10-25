"use client";

import { Bell, ChevronDown, Leaf } from "lucide-react";

interface TopNavProps {
  apiStatus: "online" | "offline" | "checking";
}

export default function TopNav({ apiStatus }: TopNavProps) {
  const statusColor =
    apiStatus === "online"
      ? "bg-green-500"
      : apiStatus === "offline"
      ? "bg-red-400"
      : "bg-amber-400";

  const statusLabel =
    apiStatus === "online" ? "Online" : apiStatus === "offline" ? "Offline" : "Checking…";

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 bg-white/80 backdrop-blur-md border-b border-gray-100 flex items-center justify-between px-5">
      {/* Left: breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-400 font-medium">MEIL Holding Apex</span>
        <span className="text-gray-300">/</span>
        <div className="flex items-center gap-1.5">
          <Leaf className="w-4 h-4 text-green-600" />
          <span className="font-semibold text-gray-800">ESG AI Engine</span>
        </div>
        {/* Status badge */}
        <div className="flex items-center gap-1.5 ml-2 px-2.5 py-0.5 rounded-full border border-gray-200 bg-gray-50">
          <span className={`w-1.5 h-1.5 rounded-full ${statusColor} ${apiStatus === "checking" ? "animate-pulse" : ""}`} />
          <span className="text-xs text-gray-500 font-medium">{statusLabel}</span>
        </div>
      </div>

      {/* Right: notification + user */}
      <div className="flex items-center gap-3">
        <button className="relative p-2 rounded-xl hover:bg-gray-100 transition-colors" aria-label="Notifications">
          <Bell className="w-4.5 h-4.5 text-gray-500" size={18} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-green-500 rounded-full" />
        </button>

        <button className="flex items-center gap-2.5 pl-1 pr-2 py-1 rounded-xl hover:bg-gray-50 transition-colors">
          {/* Avatar */}
          <div className="w-7 h-7 rounded-lg bg-green-700 flex items-center justify-center text-white text-xs font-bold">
            KR
          </div>
          <div className="text-left leading-tight hidden sm:block">
            <div className="text-xs font-semibold text-gray-800">Dr. K. Rao</div>
            <div className="text-[10px] text-gray-400">MEIL Group (Apex / Holding)</div>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
        </button>
      </div>
    </header>
  );
}
