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
import { zoom, zoomIdentity } from "d3-zoom";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface GraphNode extends SimulationNodeDatum {
  id: string;
  purchase_count: number;
  last_purchased: string | null;
  overdue: boolean;
  due_soon: boolean;
}

interface GraphLink extends SimulationLinkDatum<GraphNode> {
  weight: number;
}

/**
 * The household's purchase-history knowledge graph (knowledge/graph.py),
 * rendered as a force-directed layout: nodes are items, sized by how often
 * they've been bought and colored by restock status; edges are co-purchase
 * links, weighted by how often the two items showed up in the same order.
 */
export default function KnowledgeGraph() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [state, setState] = useState<"loading" | "empty" | "error" | "ready">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    let sim: Simulation<GraphNode, GraphLink> | null = null;

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

        svg.call(
          zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.4, 2.5])
            .on("zoom", (event) => root.attr("transform", event.transform))
        );
        svg.call(
          zoom<SVGSVGElement, unknown>().transform as never,
          zoomIdentity
        );

        const nodes: GraphNode[] = data.nodes.map((n) => ({ ...n }));
        const links: GraphLink[] = data.links.map((l) => ({ ...l }));

        sim = forceSimulation(nodes)
          .force(
            "link",
            forceLink<GraphNode, GraphLink>(links)
              .id((d) => d.id)
              .distance((d) => 90 - Math.min(d.weight, 5) * 8)
          )
          .force("charge", forceManyBody().strength(-220))
          .force("center", forceCenter(width / 2, height / 2))
          .force(
            "collide",
            forceCollide<GraphNode>((d) => 18 + Math.min(d.purchase_count, 6) * 3)
          );

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
            (d) => `kg__node ${d.overdue ? "kg__node--overdue" : d.due_soon ? "kg__node--due" : ""}`
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

        node
          .append("circle")
          .attr("r", (d) => 10 + Math.min(d.purchase_count, 6) * 3);

        node
          .append("text")
          .attr("class", "kg__label")
          .attr("dy", (d) => 10 + Math.min(d.purchase_count, 6) * 3 + 13)
          .attr("text-anchor", "middle")
          .text((d) => (d.id.length > 22 ? d.id.slice(0, 20) + "…" : d.id));

        node.append("title").text((d) => {
          const last = d.last_purchased ? new Date(d.last_purchased).toLocaleDateString() : "—";
          return `${d.id}\nBought ${d.purchase_count}×\nLast: ${last}${d.overdue ? "\nOverdue for restock" : ""}`;
        });

        sim.on("tick", () => {
          link
            .attr("x1", (d) => (d.source as GraphNode).x!)
            .attr("y1", (d) => (d.source as GraphNode).y!)
            .attr("x2", (d) => (d.target as GraphNode).x!)
            .attr("y2", (d) => (d.target as GraphNode).y!);

          node.attr("transform", (d) => `translate(${d.x},${d.y})`);
        });
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
    };
  }, []);

  return (
    <div className="kg">
      <div className="kg__head">
        <span className="kg__title">Purchase graph</span>
        <span className="kg__legend">
          <span className="kg__dot kg__dot--overdue" /> overdue
          <span className="kg__dot kg__dot--due" /> due soon
          <span className="kg__dot" /> tracked
        </span>
      </div>
      <div className="kg__canvas">
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
