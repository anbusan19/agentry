"use client";

import dynamic from "next/dynamic";

// Configured usage from the ThreeUI registry for `SylvaLivingWorldScene`,
// Living Green variant. Two deviations from the doc snippet, both required by
// Next.js:
//   1. Per-component subpath import instead of the barrel (`@designcodeio/
//      threeui`) — the barrel re-exports ~120 components, one of which imports
//      webp assets in a form Next's webpack asset loader rejects.
//   2. `ssr: false` — the scene builds a ~600 KB `srcDoc` whose inlined
//      `</script>` sequences break the streamed server render. It's a
//      decorative background, so it mounts client-side only.
import "@designcodeio/threeui/style.css";

const SylvaLivingWorldScene = dynamic(
  () =>
    import("@designcodeio/threeui/components/SylvaLivingWorldScene").then(
      (m) => m.SylvaLivingWorldScene,
    ),
  { ssr: false },
);

export function Scene() {
  return (
    <div className="shader-frame">
      <SylvaLivingWorldScene variant="living-green" />
    </div>
  );
}
