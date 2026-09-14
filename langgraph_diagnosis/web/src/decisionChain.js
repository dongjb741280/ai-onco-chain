// 决策链 A→U 的静态拓扑：节点、坐标、边（与 render.py 的 NODE_LABELS / _EDGES 对应）

export const NODES = [
  { id: 'A', label: '初诊乳腺癌', type: 'rect' },
  { id: 'B', label: '影像·病理·分子', type: 'rect' },
  { id: 'C', label: '分期与分子分型', type: 'rect' },
  { id: 'D', label: 'M 分期', type: 'diamond' },
  { id: 'E', label: '是否新辅助', type: 'diamond' },
  { id: 'F', label: '新辅助方案', type: 'rect' },
  { id: 'G', label: '直接手术', type: 'rect' },
  { id: 'H', label: '手术·病理反应', type: 'rect' },
  { id: 'I', label: 'pCR / 残余', type: 'diamond' },
  { id: 'J', label: '术后辅助', type: 'rect' },
  { id: 'K', label: '强化辅助', type: 'rect' },
  { id: 'L', label: '放疗·内分泌·抗HER2', type: 'rect' },
  { id: 'M', label: '转移灶再活检', type: 'rect' },
  { id: 'N', label: '评估既往治疗', type: 'rect' },
  { id: 'O', label: '序贯全身治疗', type: 'rect' },
  { id: 'P', label: '特殊转移部位', type: 'diamond' },
  { id: 'Q', label: '骨改良药', type: 'rect' },
  { id: 'R', label: '脑转移', type: 'diamond' },
  { id: 'R1', label: '脑实质', type: 'rect' },
  { id: 'R2', label: '脑膜', type: 'rect' },
  { id: 'S', label: '系统治疗', type: 'rect' },
  { id: 'T', label: '疗效评估·MDT', type: 'rect' },
  { id: 'U', label: '长期随访', type: 'rect' },
]

export const POS = {
  A: [600, 36], B: [600, 128], C: [600, 220], D: [600, 316],
  E: [330, 416], F: [170, 520], G: [470, 520], H: [170, 616],
  I: [170, 712], J: [90, 816], K: [250, 816], L: [330, 916],
  M: [850, 416], N: [850, 512], O: [850, 608], P: [850, 708],
  Q: [680, 816], R: [850, 816], S: [1020, 816], R1: [780, 916], R2: [950, 916],
  T: [600, 1040], U: [600, 1136],
}

export const EDGES = [
  ['A', 'B', ''], ['B', 'C', ''], ['C', 'D', ''],
  ['D', 'E', '否：M0 早期'], ['D', 'M', '是：M1 复发/转移'],
  ['E', 'F', '是'], ['E', 'G', '否'],
  ['F', 'H', ''], ['H', 'I', ''], ['G', 'J', ''],
  ['I', 'J', 'pCR'], ['I', 'K', 'non-pCR'],
  ['J', 'L', ''], ['K', 'L', ''],
  ['M', 'N', ''], ['N', 'O', ''], ['O', 'P', ''],
  ['P', 'Q', '骨转移'], ['P', 'R', '脑转移'], ['P', 'S', '其他内脏'],
  ['R', 'R1', '脑实质'], ['R', 'R2', '脑膜'],
  ['L', 'T', ''], ['Q', 'T', ''], ['R1', 'T', ''], ['R2', 'T', ''], ['S', 'T', ''],
  ['T', 'U', ''],
]

// 规范揭示顺序（点亮节点用）
export const ORDER = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'R1', 'R2', 'S', 'T', 'U']

export const NODE_BY_ID = Object.fromEntries(NODES.map((n) => [n.id, n]))

const HW = { rect: 75, diamond: 78 }
const HH = { rect: 23, diamond: 30 }

// 从 from 指向 to 的射线，在 to 节点的边界（近似矩形）处截断
export function clip(from, to, hw, hh) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len
  const tx = Math.abs(ux) > 1e-6 ? hw / Math.abs(ux) : Infinity
  const ty = Math.abs(uy) > 1e-6 ? hh / Math.abs(uy) : Infinity
  const d = Math.min(tx, ty)
  return { x: to.x - ux * d, y: to.y - uy * d }
}

export function edgeGeometry([fromId, toId]) {
  const from = { x: POS[fromId][0], y: POS[fromId][1] }
  const to = { x: POS[toId][0], y: POS[toId][1] }
  const p1 = clip(to, from, HW[NODE_BY_ID[fromId].type], HH[NODE_BY_ID[fromId].type])
  const p2 = clip(from, to, HW[NODE_BY_ID[toId].type], HH[NODE_BY_ID[toId].type])
  return { p1, p2, mid: { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 } }
}
