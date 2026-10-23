import { ErrorNotice, Loading, useResource } from "../components";

export default function RelationshipGraph({ id }) {
  const { data, error, loading, reload } = useResource("/customers/" + id + "/graph");
  if (loading) return <Loading />;
  if (error) return <ErrorNotice message={error} retry={reload} />;
  const others = data.nodes.filter((n) => n.id !== id).slice(0, 18);
  const positions = { [id]: { x: 340, y: 220 } };
  others.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, others.length);
    positions[n.id] = {
      x: 340 + 260 * Math.cos(angle),
      y: 220 + 160 * Math.sin(angle),
    };
  });
  return (
    <>
      <div className="entity-graph">
        <svg
          viewBox="0 0 680 440"
          role="img"
          aria-label="Observed customer transaction relationships"
        >
          {data.links
            .filter((l) => positions[l.source] && positions[l.target])
            .map((l, i) => (
              <line
                key={i}
                x1={positions[l.source].x}
                y1={positions[l.source].y}
                x2={positions[l.target].x}
                y2={positions[l.target].y}
                stroke="var(--graph-line)"
                strokeWidth="1.5"
              >
                <title>{l.label}</title>
              </line>
            ))}
          {data.nodes
            .filter((n) => positions[n.id])
            .map((n) => (
              <g
                key={n.id}
                transform={`translate(${positions[n.id].x},${positions[n.id].y})`}
              >
                <circle
                  r={n.id === id ? 32 : 22}
                  fill={n.id === id ? "#285f46" : "var(--soft)"}
                  stroke="var(--graph-line)"
                />
                <text
                  y="5"
                  textAnchor="middle"
                  fill={n.id === id ? "white" : "var(--text)"}
                  fontSize="11"
                >
                  {n.kind === "account_reference"
                    ? "#"
                    : n.name
                        .split(" ")
                        .map((v) => v[0])
                        .slice(0, 2)
                        .join("")}
                </text>
                <text
                  y={n.id === id ? 51 : 40}
                  textAnchor="middle"
                  fill="var(--muted)"
                  fontSize="9"
                >
                  {n.name.length > 24 ? n.name.slice(0, 23) + "…" : n.name}
                </text>
                <title>{n.name}</title>
              </g>
            ))}
        </svg>
      </div>
      <p className="subtle-note">
        {data.scope} Showing up to 18 connected nodes.
      </p>
    </>
  );
}

