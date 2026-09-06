import ChatPanel from "@/components/ChatPanel";
import KnowledgeGraph from "@/components/KnowledgeGraph";

export const metadata = {
  title: "Agentry Console",
};

export default function ConsolePage() {
  return (
    <main className="console">
      <div className="console__pane console__pane--chat">
        <ChatPanel />
      </div>
      <div className="console__pane console__pane--graph">
        <KnowledgeGraph />
      </div>
    </main>
  );
}
