"use client";

import { useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import KnowledgeGraph from "@/components/KnowledgeGraph";

/**
 * Two panes: the chat on the left, and on the right either the purchase
 * knowledge graph or — while voice mode is active — the Voice Stage, where
 * the agent's visual replies (product choices, the order summary, the paid
 * receipt) show up. The stage itself is portalled in by ChatPanel so it
 * keeps direct access to the chat's send / add-to-cart handlers; this level
 * only decides which of the two occupies the pane.
 */
export default function ConsolePage() {
  const [voiceMode, setVoiceMode] = useState(false);

  return (
    <main className="console">
      <div className="console__pane console__pane--chat">
        <ChatPanel onVoiceChange={setVoiceMode} />
      </div>
      <div className="console__pane console__pane--graph">
        {/* While voice mode is on the pane is filled by the Voice Stage,
            which ChatPanel portals in here. */}
        {!voiceMode && <KnowledgeGraph />}
      </div>
    </main>
  );
}
