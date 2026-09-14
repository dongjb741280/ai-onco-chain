import { EDGES, NODES, POS, edgeGeometry } from '../decisionChain'

export default function DecisionChain({ visitedNodes, currentNode }) {
  const visited = new Set(visitedNodes)

  return (
    <div className="canvas">
      <svg viewBox="0 0 1130 1180" role="img" aria-label="乳腺癌诊疗决策链 A 到 U 流程图">
        <g className="edges">
          {EDGES.map((e, i) => {
            const { p1, p2, mid } = edgeGeometry(e)
            const [from, to, label] = e
            const hit = visited.has(from) && visited.has(to)
            return (
              <g key={i} className={'edge' + (hit ? ' hit' : '')}>
                <path d={`M ${p1.x} ${p1.y} L ${p2.x} ${p2.y}`} />
                {label && (
                  <text x={mid.x} y={mid.y - 5} textAnchor="middle">
                    {label}
                  </text>
                )}
              </g>
            )
          })}
        </g>
        <g className="nodes">
          {NODES.map((n) => {
            const [x, y] = POS[n.id]
            const cls = 'node' + (visited.has(n.id) ? ' visited' : '') + (n.id === currentNode ? ' current' : '')
            return (
              <g key={n.id} className={cls}>
                {n.type === 'diamond' ? (
                  <polygon points={`${x},${y - 30} ${x + 78},${y} ${x},${y + 30} ${x - 78},${y}`} />
                ) : (
                  <rect x={x - 75} y={y - 23} width="150" height="46" rx="10" />
                )}
                <text className="code" x={x} y={y - 3} textAnchor="middle" fontSize="10">
                  {n.id}
                </text>
                <text className="lbl" x={x} y={y + 13} textAnchor="middle" fontSize="12">
                  {n.label}
                </text>
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}
