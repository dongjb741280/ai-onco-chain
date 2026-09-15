import { useEffect, useRef, useState } from 'react'
import useDiagnosis from './useDiagnosis'
import DecisionChain from './components/DecisionChain'
import ReviewModal from './components/ReviewModal'
import { PIPE } from './constants'
import { NODE_BY_ID } from './decisionChain'
import { esc } from './render'

const STATUS_META = {
  idle: { label: '空闲', icon: '○' },
  running: { label: '运行中', icon: null },
  paused: { label: '等待复核', icon: '⚠' },
  done: { label: '完成', icon: '✓' },
  stopped: { label: '已停止', icon: '■' },
  revised: { label: '待修改', icon: '↺' },
  error: { label: '出错', icon: '✕' },
}

function StatusBar({ status }) {
  const meta = STATUS_META[status] || STATUS_META.idle
  return (
    <div className={'status ' + status}>
      {status === 'running' ? <span className="spinner" /> : <span className="ico">{meta.icon}</span>}
      <span>{meta.label}</span>
    </div>
  )
}

function PatientStrip({ patient }) {
  const cells = []
  if (patient.name) cells.push(['患者', patient.name])
  if (patient.gender || patient.age) cells.push(['性别/年龄', `${patient.gender || '?'} · ${patient.age || '?'}岁`])
  if (patient.diagnoses && patient.diagnoses.length) cells.push(['诊断', patient.diagnoses.join('、')])
  if (patient.subtype) cells.push(['分子分型', patient.subtype])
  if (patient.staging) cells.push(['分期', patient.staging])
  if (!cells.length) return null
  return (
    <div className="patient">
      {cells.map(([k, v], i) => (
        <span className="kv" key={i}>
          <span className="k">{k}</span>
          <span className={'v' + (k === '分期' ? ' mono' : '')}>{esc(v)}</span>
        </span>
      ))}
    </div>
  )
}

function Stepper({ steps }) {
  return (
    <div className="stepper">
      {PIPE.map(([id, label]) => (
        <span key={id} className={'step' + (steps[id] ? ' ' + steps[id] : '')}>
          <span className="sdot" />
          {label}
        </span>
      ))}
    </div>
  )
}

function TraceLine({ step }) {
  const node = NODE_BY_ID[step.node] || {}
  const label = Array.isArray(node.label) ? node.label[0] : node.label || step.node
  return (
    <div className="trace-line">
      <span className="tnode">[{esc(step.node)}]</span> {esc(label)}
      {step.branch && <span className="tbranch"> ← {esc(step.branch)}</span>}
      <br />
      <span className="tev">↳ {esc(step.evidence)}</span>
    </div>
  )
}

export default function App() {
  const d = useDiagnosis()
  const [caseId, setCaseId] = useState('')
  const busy = d.status === 'running' || d.status === 'paused'
  const leftRef = useRef(null)
  const rightRef = useRef(null)

  useEffect(() => {
    if (!caseId && d.cases.length) setCaseId(d.cases[0].id)
  }, [d.cases, caseId])

  // 报告窗口默认紧凑，最高高度封顶到决策链高度
  useEffect(() => {
    const left = leftRef.current
    const right = rightRef.current
    if (!left || !right) return
    const sync = () => { right.style.maxHeight = left.offsetHeight + 'px' }
    sync()
    const ro = new ResizeObserver(sync)
    ro.observe(left)
    return () => ro.disconnect()
  }, [])

  return (
    <div className="app">
      <header>
        <div className="brand">
          <div className="mark">链</div>
          <div>
            <h1>诊疗决策链</h1>
            <div className="sub">乳腺癌 CSCO 诊疗流水线 · 前端</div>
          </div>
        </div>
        <span className={'badge' + (d.conn === 'error' ? ' err' : '')}>
          {d.conn === 'connected' ? '已连接' : d.conn === 'error' ? '后端未连接' : '连接中…'}
        </span>
        <div className="controls">
          <select value={caseId} onChange={(e) => setCaseId(e.target.value)} aria-label="选择病例">
            {d.cases.map((c) => (
              <option key={c.id} value={c.id}>{c.id} · {c.label}</option>
            ))}
          </select>
          <button className="primary" disabled={busy || d.conn !== 'connected' || !caseId} onClick={() => d.startRun(caseId)}>
            开始诊断
          </button>
          <button className="danger" disabled={!busy} onClick={d.stopRun}>停止</button>
          <StatusBar status={d.status} />
        </div>
      </header>

      <div className="activity">
        <span>{d.activity}</span>
        <span className="caret" />
      </div>

      <div className="grid">
        <div>
          <div className="panel" ref={leftRef}>
            <div className="panel-head">
              <span className="eyebrow">Decision chain</span>
              <h2>决策链 A→U</h2>
              <span className="spacer" />
              <div className="legend">
                <span className="li"><span className="sw" style={{ background: 'var(--cat-start-fill)' }} />起点</span>
                <span className="li"><span className="sw" style={{ background: 'var(--cat-decision-fill)' }} />决策</span>
                <span className="li"><span className="sw" style={{ background: 'var(--cat-early-fill)' }} />早期</span>
                <span className="li"><span className="sw" style={{ background: 'var(--cat-advanced-fill)' }} />晚期</span>
                <span className="li"><span className="sw" style={{ background: 'var(--cat-support-fill)' }} />支持</span>
              </div>
            </div>
            <PatientStrip patient={d.patient} />
            <DecisionChain visitedNodes={d.visitedNodes} currentNode={d.currentNode} />
            <Stepper steps={d.steps} />
          </div>
        </div>

        <div className="panel" ref={rightRef}>
          <div className="tabs">
            <button className={'tab' + (d.tab === 'report' ? ' active' : '')} onClick={() => d.setTab('report')}>诊断报告</button>
            <button className={'tab' + (d.tab === 'trace' ? ' active' : '')} onClick={() => d.setTab('trace')}>决策链追踪</button>
          </div>
          <div className="tab-body">
            <div hidden={d.tab !== 'report'}>
              {d.report.length === 0 ? (
                <div className="empty">运行后在此流式展示诊断报告</div>
              ) : (
                d.report.map((sec, i) => (
                  <div className="report-sec" key={i}>
                    <h3>{sec.title}</h3>
                    <div dangerouslySetInnerHTML={{ __html: sec.html }} />
                  </div>
                ))
              )}
            </div>
            <div hidden={d.tab !== 'trace'}>
              {d.trace.length === 0 ? (
                <div className="empty">运行后在此追踪决策链节点</div>
              ) : (
                d.trace.map((step, i) => <TraceLine key={i} step={step} />)
              )}
            </div>
          </div>
        </div>
      </div>

      <footer>产出自 CSCO 指南，属临床辅助，最终以主诊医师 / MDT 决策为准。</footer>

      <ReviewModal interrupt={d.interrupt} onResume={d.resume} />
    </div>
  )
}
