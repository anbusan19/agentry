"use client";

import { useEffect, useRef, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { select } from "d3-selection";
import { drag } from "d3-drag";
import { zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
// Side-effect import: augments Selection with .transition(), used by fitView.
import "d3-transition";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface GraphNode extends SimulationNodeDatum {
  id: string;
  purchase_count: number;
  last_purchased: string | null;
  overdue: boolean;
  due_soon: boolean;
  /** Every storefront this item's been bought on, most-frequent first —
   * used to color the node by its (dominant) platform. */
  platforms: string[];
  /** Per-node phase offset for the idle wander animation, so nodes don't
   * all drift in lockstep. */
  phase?: number;
}

const nodeRadius = (d: GraphNode) => 10 + Math.min(d.purchase_count, 6) * 3;

interface GraphLink extends SimulationLinkDatum<GraphNode> {
  weight: number;
}

/** CSS class for a node's dominant (most-purchased-on) platform, so the
 * circle fill reads as "which storefront this usually comes from." */
function platformClass(d: GraphNode): string {
  const platform = d.platforms?.[0];
  return platform ? `kg__node--${platform}` : "";
}

/**
 * The household's purchase-history knowledge graph (knowledge/graph.py),
 * rendered as a force-directed layout: nodes are items, sized by how often
 * they've been bought and filled by which storefront they're usually
 * bought on (kg__node--<platform>, see globals.css), with an overdue/
 * due-soon ring on top; edges are co-purchase links, weighted by how often
 * the two items showed up in the same order.
 */
export default function KnowledgeGraph() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [state, setState] = useState<"loading" | "empty" | "error" | "ready">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    let sim: Simulation<GraphNode, GraphLink> | null = null;
    let rafId: number | null = null;

    fetch(`${API_BASE}/api/graph`)
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
      })
      .then((data: { nodes: GraphNode[]; links: GraphLink[] }) => {
        if (cancelled) return;

        if (!data.nodes.length) {
          setState("empty");
          return;
        }
        setState("ready");

        const svg = select(svgRef.current!);
        svg.selectAll("*").remove();

        const width = svgRef.current!.clientWidth || 600;
        const height = svgRef.current!.clientHeight || 600;

        const root = svg.append("g");

        const zoomBehavior: ZoomBehavior<SVGSVGElement, unknown> = zoom<SVGSVGElement, unknown>()
          .scaleExtent([0.3, 2.5])
          .on("zoom", (event) => root.attr("transform", event.transform));
        svg.call(zoomBehavior);
        svg.call(zoomBehavior.transform, zoomIdentity);

        const nodes: GraphNode[] = data.nodes.map((n) => ({ ...n, phase: Math.random() * Math.PI * 2 }));
        const links: GraphLink[] = data.links.map((l) => ({ ...l }));

        const reducedMotion =
          typeof window !== "undefined" &&
          window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        sim = forceSimulation(nodes)
          .force(
            "link",
            forceLink<GraphNode, GraphLink>(links)
              .id((d) => d.id)
              .distance((d) => 90 - Math.min(d.weight, 5) * 8)
          )
          .force("charge", forceManyBody().strength(-220))
          .force("center", forceCenter(width / 2, height / 2))
          .force("collide", forceCollide<GraphNode>((d) => nodeRadius(d) + 8));

        const link = root
          .append("g")
          .attr("class", "kg__links")
          .selectAll("line")
          .data(links)
          .join<SVGLineElement>("line")
          .attr("class", "kg__link")
          .attr("stroke-width", (d) => Math.min(1 + d.weight * 0.8, 6));

        const node = root
          .append("g")
          .attr("class", "kg__nodes")
          .selectAll("g")
          .data(nodes)
          .join<SVGGElement>("g")
          .attr(
            "class",
            (d) =>
              `kg__node ${platformClass(d)} ${d.overdue ? "kg__node--overdue" : d.due_soon ? "kg__node--due" : ""}`
          )
          .call(
            drag<SVGGElement, GraphNode>()
              .on("start", (event, d) => {
                if (!event.active) sim?.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
              })
              .on("drag", (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
              })
              .on("end", (event, d) => {
                if (!event.active) sim?.alphaTarget(0);
                d.fx = null;
                d.fy = null;
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              }) as unknown as (selection: any) => void
          );

        node.append("circle").attr("r", nodeRadius);

        node
          .append("text")
          .attr("class", "kg__label")
          .attr("dy", (d) => nodeRadius(d) + 13)
          .attr("text-anchor", "middle")
          .text((d) => (d.id.length > 22 ? d.id.slice(0, 20) + "…" : d.id));

        node.append("title").text((d) => {
          const last = d.last_purchased ? new Date(d.last_purchased).toLocaleDateString() : "—";
          return `${d.id}\nBought ${d.purchase_count}×\nLast: ${last}${d.overdue ? "\nOverdue for restock" : ""}`;
        });

        // Fit the whole graph into view, once its layout has settled.
        const fitView = () => {
          const el = svgRef.current;
          if (!el || !nodes.length) return;

          const w = el.clientWidth || width;
          const h = el.clientHeight || height;
          const pad = 60;

          const xs = nodes.map((d) => d.x ?? 0);
          const ys = nodes.map((d) => d.y ?? 0);
          const minX = Math.min(...xs) - pad;
          const maxX = Math.max(...xs) + pad;
          const minY = Math.min(...ys) - pad;
          const maxY = Math.max(...ys) + pad;

          const scale = Math.min(2.5, Math.max(0.3, Math.min(w / (maxX - minX || 1), h / (maxY - minY || 1))));
          const tx = w / 2 - scale * (minX + maxX) / 2;
          const ty = h / 2 - scale * (minY + maxY) / 2;

          svg
            .transition()
            .duration(650)
            .call(zoomBehavior.transform, zoomIdentity.translate(tx, ty).scale(scale));
        };

        // Only auto-fit on the graph's initial settle — not after every
        // drag interaction restarts and re-settles the simulation, which
        // would otherwise snap away any manual pan/zoom mid-inspection.
        let hasFitOnce = false;
        sim.on("end", () => {
          if (hasFitOnce) return;
          hasFitOnce = true;
          fitView();
        });

        // Render loop: reads live node positions every frame (so it shows
        // the layout settling in, not just a teleport to the final spot),
        // then keeps a slight idle wander going afterwards so the graph
        // never reads as a static, dead diagram.
        const WANDER_PX = 4;
        const WANDER_SPEED = 0.0007;

        const renderFrame = (t: number) => {
          const wobble = reducedMotion ? 0 : WANDER_PX;
          const wx = (d: GraphNode) => (d.x ?? 0) + wobble * Math.sin(t * WANDER_SPEED + (d.phase ?? 0));
          const wy = (d: GraphNode) => (d.y ?? 0) + wobble * Math.cos(t * WANDER_SPEED * 1.3 + (d.phase ?? 0));

          link
            .attr("x1", (d) => wx(d.source as GraphNode))
            .attr("y1", (d) => wy(d.source as GraphNode))
            .attr("x2", (d) => wx(d.target as GraphNode))
            .attr("y2", (d) => wy(d.target as GraphNode));

          node.attr("transform", (d) => `translate(${wx(d)},${wy(d)})`);

          rafId = requestAnimationFrame(renderFrame);
        };
        rafId = requestAnimationFrame(renderFrame);
      })
      .catch((err) => {
        if (!cancelled) {
          setState("error");
          setErrorMessage(err.message || "Could not reach the agent server.");
        }
      });

    return () => {
      cancelled = true;
      sim?.stop();
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <div className="kg">
      <div className="kg__head">
        <span className="kg__title">Purchase graph</span>
      </div>
      <div className="kg__canvas">
        <span className="kg__legend">
          <span className="kg__dot kg__dot--overdue" /> overdue
          <span className="kg__dot kg__dot--due" /> due soon
          <span className="kg__dot kg__dot--zepto" /> zepto
          <span className="kg__dot kg__dot--blinkit" /> blinkit
          <span className="kg__dot kg__dot--instamart" /> instamart
        </span>
        {state === "empty" && (
          <p className="kg__note">
            No purchases recorded yet — the graph fills in as orders complete.
          </p>
        )}
        {state === "error" && (
          <p className="kg__note kg__note--error">
            Couldn&apos;t load the graph: {errorMessage}
            <br />
            Is <code>uvicorn server:app --port 8000</code> running?
          </p>
        )}
        <svg ref={svgRef} className="kg__svg" />
      </div>
    </div>
  );
}
