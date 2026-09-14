// The deck itself is a client component (slide index + keyboard nav state),
// so page-level metadata lives here in a server layout instead — same
// pattern as app/console/layout.tsx.
export const metadata = {
  title: "Agentry — Pitch Deck",
};

export default function PitchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
