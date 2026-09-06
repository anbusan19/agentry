// The console page itself is a client component (it holds voice-mode
// state shared between the chat and the right-hand pane), so page-level
// metadata lives here in a server layout instead.
export const metadata = {
  title: "Agentry Console",
};

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return children;
}
