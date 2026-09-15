import { EDGES, NODES, POS, edgeGeometry } from '../decisionChain'

const VIEWBOX = '0 0 920 1400'
const LINE_H = 14

export default function DecisionChain({ visitedNodes, currentNode }) {
  const visited = new Set(visitedNodes)

  return (
    <div className="canvas">
      <svg viewBox={VIEWBOX} role="img" aria-label="乳腺癌诊疗决策链 A 到 U 流程图">
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
            const cls =
              'node cat-' + n.cat + (visited.has(n.id) ? ' visited' : '') + (n.id === currentNode ? ' current' : '')
            const lines = n.label
            const codeY = n.type === 'diamond' ? y - 28 : y - 18
            const startY = y - ((lines.length - 1) * LINE_H) / 2 + 6
            return (
              <g key={n.id} className={cls}>
                {n.type === 'diamond' ? (
                  <polygon points={`${x},${y - 42} ${x + 86},${y} ${x},${y + 42} ${x - 86},${y}`} />
                ) : (
                  <rect x={x - 75} y={y - 30} width="150" height="60" rx="11" />
                )}
                <text className="code" x={x} y={codeY} textAnchor="middle" fontSize="8.5">
                  {n.id}
                </text>
                {lines.map((ln, li) => (
                  <text key={li} className="lbl" x={x} y={startY + li * LINE_H} textAnchor="middle" fontSize="11">
                    {ln}
                  </text>
                ))}
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}
