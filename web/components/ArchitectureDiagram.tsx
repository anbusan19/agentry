"use client";

import { useEffect, useRef, useState } from "react";

import { KnowledgeGraphOrb } from "./KnowledgeGraphOrb";

/** stagger index as a CSS custom property (csstype rejects `--*` in a literal) */
const vi = (i: number): React.CSSProperties =>
  ({ "--i": i }) as Record<string, number> as React.CSSProperties;

/* ── brand marks ───────────────────────────────────────────────────────────
   Gemini / Telegram / Python: single-path simple-icons glyphs (24x24).
   Playwright + the AWS wordmark: multi-path devicon art (128x128).
   All inlined — the diagram makes no network request. */

function GeminiLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="#8E75B2"
        d="M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81"
      />
    </svg>
  );
}

function PythonLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="#7CA8CE"
        d="M14.25.18l.9.2.73.26.59.3.45.32.34.34.25.34.16.33.1.3.04.26.02.2-.01.13V8.5l-.05.63-.13.55-.21.46-.26.38-.3.31-.33.25-.35.19-.35.14-.33.1-.3.07-.26.04-.21.02H8.77l-.69.05-.59.14-.5.22-.41.27-.33.32-.27.35-.2.36-.15.37-.1.35-.07.32-.04.27-.02.21v3.06H3.17l-.21-.03-.28-.07-.32-.12-.35-.18-.36-.26-.36-.36-.35-.46-.32-.59-.28-.73-.21-.88-.14-1.05-.05-1.23.06-1.22.16-1.04.24-.87.32-.71.36-.57.4-.44.42-.33.42-.24.4-.16.36-.1.32-.05.24-.01h.16l.06.01h8.16v-.83H6.18l-.01-2.75-.02-.37.05-.34.11-.31.17-.28.25-.26.31-.23.38-.2.44-.18.51-.15.58-.12.64-.1.71-.06.77-.04.84-.02 1.27.05zm-6.3 1.98l-.23.33-.08.41.08.41.23.34.33.22.41.09.41-.09.33-.22.23-.34.08-.41-.08-.41-.23-.33-.33-.22-.41-.09-.41.09zm13.09 3.95l.28.06.32.12.35.18.36.27.36.35.35.47.32.59.28.73.21.88.14 1.04.05 1.23-.06 1.23-.16 1.04-.24.86-.32.71-.36.57-.4.45-.42.33-.42.24-.4.16-.36.09-.32.05-.24.02-.16-.01h-8.22v.82h5.84l.01 2.76.02.36-.05.34-.11.31-.17.29-.25.25-.31.24-.38.2-.44.17-.51.15-.58.13-.64.09-.71.07-.77.04-.84.01-1.27-.04-1.07-.14-.9-.2-.73-.25-.59-.3-.45-.33-.34-.34-.25-.34-.16-.33-.1-.3-.04-.25-.02-.2.01-.13v-5.34l.05-.64.13-.54.21-.46.26-.38.3-.32.33-.24.35-.2.35-.14.33-.1.3-.06.26-.04.21-.02.13-.01h5.84l.69-.05.59-.14.5-.21.41-.28.33-.32.27-.35.2-.36.15-.36.1-.35.07-.32.04-.28.02-.21V6.07h2.09l.14.01zm-6.47 14.25l-.23.33-.08.41.08.41.23.33.33.23.41.08.41-.08.33-.23.23-.33.08-.41-.08-.41-.23-.33-.33-.23-.41-.08-.41.08z"
      />
    </svg>
  );
}

function TelegramLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="#2AABEE"
        d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"
      />
    </svg>
  );
}

function PlaywrightLogo({ className }: { className?: string }) {
  const P: [string, string][] = [
    ["#2D4552", "M43.662 70.898c-4.124 1.17-6.829 3.222-8.611 5.272 1.707-1.494 3.993-2.865 7.077-3.739 3.155-.894 5.846-.888 8.069-.459v-1.739c-1.897-.173-4.072-.035-6.536.664ZM34.863 56.28l-15.314 4.035s.279.394.796.92l12.984-3.421s-.184 2.371-1.782 4.492c3.022-2.287 3.316-6.025 3.316-6.025Zm12.819 35.991C26.131 98.076 14.729 73.1 11.277 60.137 9.682 54.153 8.986 49.621 8.8 46.697a4.955 4.955 0 0 1 .011-.794c-1.118.068-1.653.649-1.544 2.328.186 2.923.882 7.454 2.477 13.44 3.45 12.961 14.854 37.937 36.405 32.132 4.691-1.264 8.215-3.565 10.86-6.504-2.438 2.202-5.49 3.937-9.327 4.972Zm-8.799-14.618l-15.314 4.035s.279.394.796.92l12.984-3.421s-.184 2.371-1.782 4.492c3.022-2.287 3.316-6.025 3.316-6.025Zm12.819 35.991"],
    ["#2D4552", "M62.074 53.627c3.802 1.08 5.812 3.745 6.875 6.104l4.239 1.204s-.578-8.255-8.045-10.376c-6.985-1.985-11.284 3.881-11.807 4.64 2.032-1.448 4.999-2.633 8.738-1.572Zm33.741 6.142c-6.992-1.994-11.289 3.884-11.804 4.633 2.034-1.446 4.999-2.632 8.737-1.566 3.796 1.081 5.804 3.743 6.87 6.104l4.245 1.208s-.588-8.257-8.048-10.379Zm-4.211 21.766-35.261-9.858s.382 1.935 1.846 4.441l29.688 8.3c2.444-1.414 3.726-2.883 3.726-2.883Zm-24.446 21.218c-27.92-7.485-24.544-43.059-20.027-59.916 1.86-6.947 3.772-12.11 5.358-15.572-.946-.195-1.73.304-2.504 1.878-1.684 3.415-3.837 8.976-5.921 16.76-4.516 16.857-7.892 52.429 20.027 59.914 13.159 3.525 23.411-1.833 31.053-10.247-7.254 6.57-16.515 10.253-27.986 7.182Z"],
    ["#E2574C", "M51.732 83.935v-7.179l-19.945 5.656s1.474-8.563 11.876-11.514c3.155-.894 5.846-.888 8.069-.459V40.995h9.987c-1.087-3.36-2.139-5.947-3.023-7.744-1.461-2.975-2.96-1.003-6.361 1.842-2.396 2.001-8.45 6.271-17.561 8.726-9.111 2.457-16.476 1.805-19.55 1.273-4.357-.752-6.636-1.708-6.422 1.605.186 2.923.882 7.455 2.477 13.44 3.45 12.962 14.854 37.937 36.405 32.132 5.629-1.517 9.603-4.515 12.357-8.336h-8.309v.002Zm-32.185-23.62 15.316-4.035s-.446 5.892-6.188 7.405c-5.743 1.512-9.128-3.371-9.128-3.371Z"],
    ["#2EAD33", "M109.372 41.336c-3.981.698-13.532 1.567-25.336-1.596-11.807-3.162-19.64-8.692-22.744-11.292-4.4-3.685-6.335-6.246-8.24-2.372-1.684 3.417-3.837 8.977-5.921 16.762-4.516 16.857-7.892 52.429 20.027 59.914 27.912 7.479 42.772-25.017 47.289-41.875 2.084-7.783 2.998-13.676 3.25-17.476.287-4.305-2.67-3.055-8.324-2.064ZM53.28 55.282s4.4-6.843 11.862-4.722c7.467 2.121 8.045 10.376 8.045 10.376L53.28 55.282Zm18.215 30.706c-13.125-3.845-15.15-14.311-15.15-14.311l35.259 9.858c0-.002-7.117 8.25-20.109 4.453Zm12.466-21.51s4.394-6.838 11.854-4.711c7.46 2.124 8.048 10.379 8.048 10.379l-19.902-5.668Z"],
    ["#D65348", "M44.762 78.733 31.787 82.41s1.41-8.029 10.968-11.212l-7.347-27.573-.635.193c-9.111 2.457-16.476 1.805-19.55 1.273-4.357-.751-6.636-1.708-6.422 1.606.186 2.923.882 7.454 2.477 13.44 3.45 12.961 14.854 37.937 36.405 32.132l.635-.199-3.555-13.337ZM19.548 60.315l15.316-4.035s-.446 5.892-6.188 7.405c-5.743 1.512-9.128-3.371-9.128-3.371Z"],
    ["#1D8D22", "m72.086 86.132-.594-.144c-13.125-3.844-15.15-14.311-15.15-14.311l18.182 5.082L84.15 39.77l-.116-.031c-11.807-3.162-19.64-8.692-22.744-11.292-4.4-3.685-6.335-6.246-8.24-2.372-1.682 3.417-3.836 8.977-5.92 16.762-4.516 16.857-7.892 52.429 20.027 59.914l.572.129 4.357-16.748Zm-18.807-30.85s4.4-6.843 11.862-4.722c7.467 2.121 8.045 10.376 8.045 10.376l-19.907-5.654Z"],
    ["#C04B41", "m45.423 78.544-3.48.988c.822 4.634 2.271 9.082 4.545 13.011.396-.087.788-.163 1.192-.273a25.224 25.224 0 0 0 2.98-1.023c-2.541-3.771-4.222-8.114-5.237-12.702Zm-1.359-32.64c-1.788 6.674-3.388 16.28-2.948 25.915a20.061 20.061 0 0 1 2.546-.923l.644-.144c-.785-10.292.912-20.78 2.825-27.915a139.404 139.404 0 0 1 1.455-5.05 45.171 45.171 0 0 1-2.578 1.53 132.234 132.234 0 0 0-1.944 6.587Z"],
  ];
  return (
    <svg viewBox="0 0 128 128" className={className} aria-hidden="true">
      {P.map(([f, d], i) => (
        <path key={i} d={d} fill={f} />
      ))}
    </svg>
  );
}

function AwsLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 128 128" className={className} aria-hidden="true">
      <path
        fill="#FF9900"
        d="M108.59 26.148c-1.852 0-3.622.211-5.305.715-1.684.504-3.117 1.223-4.379 2.188a10.829 10.829 0 0 0-3.031 3.453c-.757 1.348-1.137 2.906-1.137 4.676 0 2.187.716 4.25 2.106 6.105 1.386 1.895 3.66 3.324 6.734 4.293l6.106 1.895c2.062.675 3.496 1.391 4.254 2.191.757.801 1.136 1.765 1.136 2.945 0 1.726-.758 3.074-2.191 4-1.43.925-3.492 1.391-6.145 1.391-1.687 0-3.328-.168-5.011-.504a23.102 23.102 0 0 1-4.633-1.476c-.421-.168-.801-.336-1.051-.418a2.357 2.357 0 0 0-.758-.13c-.634 0-.969.423-.969 1.305v2.149a2.919 2.919 0 0 0 .254 1.18c.168.38.629.8 1.305 1.18 1.094.628 2.734 1.179 4.84 1.683 2.105.504 4.297.758 6.484.758 2.15 0 4.129-.297 6.024-.883 1.808-.551 3.367-1.309 4.672-2.36 1.304-1.01 2.316-2.273 3.074-3.707.714-1.429 1.094-3.07 1.094-4.882 0-2.188-.633-4.168-1.938-5.895-1.304-1.727-3.491-3.074-6.523-4.043l-5.98-1.895c-2.23-.713-3.79-1.516-4.634-2.316-.84-.797-1.261-1.808-1.261-2.988 0-1.726.671-2.95 1.98-3.746 1.305-.801 3.199-1.18 5.598-1.18 2.988 0 5.683.547 8.086 1.64.714.337 1.261.508 1.597.508.633 0 .969-.463.969-1.347v-1.98c0-.59-.125-1.051-.379-1.391-.25-.378-.672-.715-1.262-1.051-.422-.254-1.011-.504-1.77-.758a32.528 32.528 0 0 0-2.398-.676c-.886-.168-1.769-.336-2.738-.46a21.347 21.347 0 0 0-2.82-.169zm-86.822.082c-2.316 0-4.508.254-6.57.801-2.063.505-3.831 1.137-5.303 1.895-.59.297-.97.59-1.18.883-.211.296-.293.8-.293 1.476v2.063c0 .882.293 1.304.883 1.304.168 0 .378-.043.674-.125.293-.086.796-.254 1.472-.547a33.416 33.416 0 0 1 4.547-1.433A19.176 19.176 0 0 1 20.547 32c3.242 0 5.513.633 6.863 1.938 1.304 1.303 1.98 3.534 1.98 6.734v3.074c-1.683-.379-3.283-.715-4.843-.926-1.558-.21-3.031-.336-4.461-.336-4.34 0-7.75 1.094-10.316 3.286-2.571 2.187-3.832 5.093-3.832 8.671 0 3.368 1.05 6.063 3.113 8.086 2.066 2.02 4.887 3.032 8.422 3.032 4.97 0 9.097-1.938 12.379-5.813a34.153 34.153 0 0 0 1.304 2.484 13.28 13.28 0 0 0 1.516 1.98c.422.38.844.59 1.266.59.334 0 .714-.128 1.093-.378l2.653-1.77c.546-.42.8-.843.8-1.261a1.86 1.86 0 0 0-.293-.97 22.469 22.469 0 0 1-1.347-3.03c-.297-.925-.465-2.19-.465-3.75h-.086V40c0-4.633-1.176-8.086-3.492-10.36-2.36-2.273-6.025-3.41-11.033-3.41zm19.58 1.012c-.676 0-1.012.379-1.012 1.051 0 .297.129.844.379 1.687l9.894 32.547c.254.8.547 1.387.887 1.641.336.297.84.422 1.598.422h3.62c.759 0 1.347-.125 1.684-.422.34-.293.591-.84.801-1.684l6.485-27.117 6.527 27.16c.168.84.46 1.387.8 1.684.337.292.883.422 1.684.422h3.621c.715 0 1.262-.167 1.598-.422.34-.253.633-.8.887-1.64L90.949 30.02c.168-.46.25-.797.293-1.051.043-.254.086-.466.086-.676 0-.715-.379-1.05-1.055-1.05H86.36c-.757 0-1.308.166-1.644.421-.293.25-.59.8-.84 1.64L76.59 57.517l-6.653-28.211c-.166-.8-.464-1.39-.8-1.64-.336-.298-.884-.423-1.684-.423h-3.367c-.758 0-1.348.167-1.688.422-.335.25-.588.8-.796 1.64l-6.57 27.876-7.075-27.875c-.25-.8-.504-1.39-.84-1.64-.297-.298-.844-.423-1.644-.423h-4.125zM21.64 47.496a31.816 31.816 0 0 1 3.96.25 34.401 34.401 0 0 1 3.872.719v1.765c0 1.435-.168 2.653-.422 3.665-.25 1.01-.758 1.895-1.43 2.695-1.137 1.262-2.484 2.187-4 2.695-1.516.504-2.949.758-4.336.758-1.937 0-3.41-.508-4.422-1.559-1.054-1.01-1.558-2.484-1.558-4.464 0-2.106.675-3.704 2.062-4.84 1.391-1.137 3.454-1.684 6.274-1.684zM118 73.348c-4.432.063-9.664 1.052-13.621 3.832-1.223.883-1.012 2.062.336 1.894 4.508-.547 14.44-1.726 16.21.547 1.77 2.23-1.976 11.62-3.663 15.79-.504 1.26.59 1.769 1.726.8 7.41-6.231 9.348-19.242 7.832-21.137-.757-.925-4.388-1.79-8.82-1.726zM1.63 75.859c-.926.116-1.347 1.236-.368 2.121 16.508 14.902 38.359 23.872 62.613 23.872 17.305 0 37.43-5.43 51.281-15.66 2.273-1.689.298-4.254-2.02-3.204-15.533 6.57-32.421 9.77-47.788 9.77-22.778 0-44.8-6.273-62.653-16.633-.39-.231-.755-.304-1.064-.266z"
      />
    </svg>
  );
}

/* small generic glyphs (no brand) — matched to the paper-dim stroke look */
const Glyph = {
  intent: (
    <svg viewBox="0 0 24 24" className="arch__ico" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3" />
    </svg>
  ),
  graph: (
    <svg viewBox="0 0 24 24" className="arch__ico" aria-hidden="true">
      <circle cx="5" cy="6" r="2.4" />
      <circle cx="19" cy="5" r="2.4" />
      <circle cx="13" cy="19" r="2.4" />
      <path d="M7 7.6 11.4 17M7.2 5.4 16.6 4.6M17.6 7l-3.4 9.8" />
    </svg>
  ),
  cart: (
    <svg viewBox="0 0 24 24" className="arch__ico" aria-hidden="true">
      <path d="M2 4h3l2.4 12.5h11L21 8H6.2" />
      <circle cx="9" cy="20" r="1.6" />
      <circle cx="18" cy="20" r="1.6" />
    </svg>
  ),
  wallet: (
    <svg viewBox="0 0 24 24" className="arch__ico" aria-hidden="true">
      <rect x="2.5" y="5" width="19" height="14" rx="3" />
      <path d="M16 12h4" />
    </svg>
  ),
};

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="arch__li">
      <span className="arch__dot" />
      {children}
    </li>
  );
}

/* Anchor coordinates are tied to the fixed node rectangles in globals.css
   (.arch__node--*): each path leaves one card border and lands on another, in
   the 1200 x 872 stage coordinate space. Strands Agent is the hub at centre,
   with Telegram above, Goal left, Playwright below, Storefront right. */
const LINKS = {
  goalAgent: "M336 445 C 384 445, 388 430, 436 430",
  agentTelegram: "M602 300 L602 242",
  agentBrowser: "M602 592 L602 646",
  browserStore: "M752 704 C 852 704, 918 690, 918 572",
  storeAgent: "M1020 322 C 1030 206, 880 246, 768 336",
  storeMemory: "M1160 447 L1240 447",
};

export function ArchitectureDiagram() {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.2 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <figure className="arch">
      <div className="arch__head">
        <span className="arch__head-rule" />
        <span className="arch__head-label">Agent workflow</span>
      </div>

      <div className="arch__scroll">
        <div
          ref={ref}
          className="arch__stage"
          data-visible={visible ? "true" : "false"}
        >
          {/* AWS runtime — the outline container around every node */}
          <div className="arch__enclosure">
            <span className="arch__enclosure-tag">
              <AwsLogo className="arch__aws" />
              Stretch &middot; Bedrock AgentCore Runtime
            </span>
          </div>

          {/* GOAL (left) */}
          <div className="arch__node arch__node--goal" style={vi(1)}>
            <div className="arch__card">
              <div className="arch__card-head">
                <span className="arch__ico-wrap">{Glyph.intent}</span>
                <span className="arch__badge">Intent</span>
              </div>
              <h3>Goal</h3>
              <ul className="arch__list">
                <Bullet>Plain-language brief &mdash; &ldquo;restock the pantry&rdquo;</Bullet>
                <Bullet>Resolved into a concrete cart, budget and substitutes</Bullet>
              </ul>
            </div>
            <div className="arch__step">
              <span className="arch__step-rule" />
              Step 01
            </div>
          </div>

          {/* STRANDS AGENT (hub, centre) */}
          <div className="arch__node arch__node--agent" style={vi(0)}>
            <div className="arch__card arch__card--hub">
              <div className="arch__card-head">
                <span className="arch__logos">
                  <GeminiLogo className="arch__logo" />
                  <PythonLogo className="arch__logo" />
                </span>
                <span className="arch__badge arch__badge--accent">Orchestration</span>
              </div>
              <h3>Strands Agent</h3>
              <p>
                Plans the run, calls tools in a loop, and reflects on each
                result &mdash; with a local knowledge graph for past orders.
              </p>
              <pre className="arch__code">
{`Agent(
  model=GeminiModel(...),
  tools=[browser, telegram, cart],
)`}
              </pre>
            </div>
          </div>

          {/* PLAYWRIGHT (below the hub) */}
          <div className="arch__node arch__node--browser" style={vi(3)}>
            <div className="arch__card">
              <div className="arch__card-head">
                <span className="arch__logos">
                  <PlaywrightLogo className="arch__logo" />
                </span>
                <span className="arch__badge">Browser</span>
              </div>
              <h3>Playwright</h3>
              <p>
                Stealth Chromium on a live quick-commerce storefront &mdash; search,
                compare, add to cart, ride out DOM changes.
              </p>
            </div>
            <div className="arch__step">
              <span className="arch__step-rule" />
              Step 02
            </div>
          </div>

          {/* TELEGRAM (above the hub) */}
          <div className="arch__node arch__node--telegram" style={vi(2)}>
            <div className="arch__card">
              <div className="arch__card-head">
                <span className="arch__logos">
                  <TelegramLogo className="arch__logo" />
                </span>
                <span className="arch__badge">Human-in-the-loop</span>
              </div>
              <h3>Telegram</h3>
              <p>
                One thread, used only when a person must decide &mdash; a missing
                staple, a price past the cap.
              </p>
            </div>
          </div>

          {/* STOREFRONT + WALLET (right) */}
          <div className="arch__node arch__node--fulfil" style={vi(4)}>
            <div className="arch__card">
              <div className="arch__card-head">
                <span className="arch__ico-wrap">{Glyph.cart}</span>
                <span className="arch__badge">Fulfilment</span>
              </div>
              <h3>Storefront &amp; Wallet</h3>
              <ul className="arch__list">
                <Bullet>Cart assembled on the real Zepto storefront</Bullet>
                <Bullet>
                  <span className="arch__inline-ico">{Glyph.wallet}</span>
                  Checkout paid from platform cash &mdash; no card, no chain
                </Bullet>
                <Bullet>Order lands; a Telegram receipt closes the loop</Bullet>
              </ul>
            </div>
            <div className="arch__step">
              <span className="arch__step-rule" />
              Step 03 &middot; done
            </div>
          </div>

          {/* KNOWLEDGE GRAPH (memory, inside the runtime container) */}
          <div className="arch__node arch__node--memory" style={vi(5)}>
            <div className="arch__card">
              <div className="arch__card-head">
                <span className="arch__ico-wrap">{Glyph.graph}</span>
                <span className="arch__badge">Memory</span>
              </div>
              <h3>Knowledge graph</h3>
              <div className="arch__orb">
                <KnowledgeGraphOrb />
              </div>
              <p>
                Past orders &mdash; items, brands, prices, accepted substitutes
                &mdash; read and written on every run.
              </p>
            </div>
          </div>

          {/* ── connector overlay ─────────────────────────────────── */}
          <svg
            className="arch__lines"
            viewBox="0 0 1564 872"
            aria-hidden="true"
          >
            <defs>
              <marker
                id="arch-arrow"
                markerWidth="9"
                markerHeight="9"
                refX="7"
                refY="3.2"
                orient="auto"
              >
                <path d="M0 0 L7 3.2 L0 6.4" fill="none" stroke="currentColor" strokeWidth="1.1" />
              </marker>
            </defs>

            <path className="arch__link" style={vi(1)} pathLength={1} d={LINKS.goalAgent} markerEnd="url(#arch-arrow)" />
            <path className="arch__link arch__link--dash arch__link--accent" style={vi(2)} pathLength={1} d={LINKS.agentTelegram} markerEnd="url(#arch-arrow)" />
            <path className="arch__link" style={vi(3)} pathLength={1} d={LINKS.agentBrowser} markerEnd="url(#arch-arrow)" />
            <path className="arch__link" style={vi(3)} pathLength={1} d={LINKS.browserStore} markerEnd="url(#arch-arrow)" />
            <path className="arch__link arch__link--dash arch__link--return" style={vi(4)} pathLength={1} d={LINKS.storeAgent} />
            <path className="arch__link arch__link--dash" style={vi(5)} pathLength={1} d={LINKS.storeMemory} markerEnd="url(#arch-arrow)" />

            <text className="arch__linelabel" x={386} y={424} textAnchor="middle">goal + budget</text>
            <text className="arch__linelabel arch__linelabel--accent" x={618} y={268}>escalate</text>
            <text className="arch__linelabel" x={618} y={622}>drive</text>
            <text className="arch__linelabel" x={806} y={664} textAnchor="middle">checkout</text>
            <text className="arch__linelabel arch__linelabel--return" x={904} y={224}>order result</text>
            <text className="arch__linelabel" x={1200} y={436} textAnchor="middle">history</text>
          </svg>
        </div>
      </div>

      <figcaption className="arch__caption">
        Strands Agents SDK &middot; Gemini &middot; Python &middot; Playwright &middot; Telegram Bot API &middot; AWS Bedrock AgentCore
      </figcaption>
    </figure>
  );
}
