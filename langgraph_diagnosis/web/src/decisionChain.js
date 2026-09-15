// 决策链 A→U 静态拓扑：节点、坐标、边
//
// 节点类别（cat）与参考图 breast-cancer-treatment-decision-chain 一致：
//   start(A) / decision(D,E,I,P,R) / early(F,G,H,J,K,L) / advanced(M,N,O,Q,R1,R2,S) / support(T,U)
//   default(B,C) 中性
//
// 布局：横向适配 panel 宽度（无横向滚动），竖向可延展。

export const NODES = [
  { id: 'A', cat: 'start', type: 'rect', label: ['初诊乳腺癌'] },
  { id: 'B', cat: 'default', type: 'rect', label: ['影像·病理·分子标志物'] },
  { id: 'C', cat: 'default', type: 'rect', label: ['TNM分期·分子分型'] },
  { id: 'D', cat: 'decision', type: 'diamond', label: ['M分期：远处转移?'] },
  { id: 'E', cat: 'decision', type: 'diamond', label: ['适合新辅助?'] },
  { id: 'F', cat: 'early', type: 'rect', label: ['按亚型选新辅助', 'HER2+双靶/三阴/HR+'] },
  { id: 'G', cat: 'early', type: 'rect', label: ['直接手术', '腋窝评估'] },
  { id: 'H', cat: 'early', type: 'rect', label: ['手术·病理反应'] },
  { id: 'I', cat: 'decision', type: 'diamond', label: ['pCR / 残余?'] },
  { id: 'J', cat: 'early', type: 'rect', label: ['按风险术后辅助'] },
  { id: 'K', cat: 'early', type: 'rect', label: ['强化辅助', 'T-DM1 / T-DXd'] },
  { id: 'L', cat: 'early', type: 'rect', label: ['放疗·内分泌·抗HER2'] },
  { id: 'M', cat: 'advanced', type: 'rect', label: ['转移灶再活检·再分型'] },
  { id: 'N', cat: 'advanced', type: 'rect', label: ['评估既往治疗·治疗线'] },
  { id: 'O', cat: 'advanced', type: 'rect', label: ['按亚型序贯全身治疗'] },
  { id: 'P', cat: 'decision', type: 'diamond', label: ['特殊转移部位?'] },
  { id: 'Q', cat: 'advanced', type: 'rect', label: ['骨改良药 + 局部治疗'] },
  { id: 'R', cat: 'decision', type: 'diamond', label: ['脑转移：实质/脑膜?'] },
  { id: 'R1', cat: 'advanced', type: 'rect', label: ['脑实质：SRS/FSRT'] },
  { id: 'R2', cat: 'advanced', type: 'rect', label: ['脑膜：全中枢/鞘内'] },
  { id: 'S', cat: 'advanced', type: 'rect', label: ['继续系统治疗'] },
  { id: 'T', cat: 'support', type: 'rect', label: ['疗效评估·毒性·MDT'] },
  { id: 'U', cat: 'support', type: 'rect', label: ['长期随访·复发监测'] },
]

export const POS = {
  A: [440, 40], B: [440, 150], C: [440, 260], D: [440, 380],
  E: [250, 500], F: [90, 620], G: [250, 620], H: [90, 740],
  I: [90, 860], J: [250, 980], K: [90, 980], L: [170, 1100],
  M: [660, 500], N: [660, 620], O: [660, 740], P: [660, 860],
  Q: [500, 980], R: [660, 980], S: [820, 980], R1: [600, 1100], R2: [760, 1100],
  T: [440, 1240], U: [440, 1360],
}

export const EDGES = [
  ['A', 'B', ''], ['B', 'C', ''], ['C', 'D', ''],
  ['D', 'E', '否：M0'], ['D', 'M', '是：M1'],
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

const HW = { rect: 75, diamond: 86 }
const HH = { rect: 30, diamond: 42 }

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
