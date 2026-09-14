import { useCallback, useEffect, useRef, useState } from 'react'
import { ORDER } from './decisionChain'
import { reportSections } from './render'
import { PIPE_LABEL } from './constants'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export default function useDiagnosis() {
  const [cases, setCases] = useState([])
  const [conn, setConn] = useState('connecting') // connecting | connected | error
  const [status, setStatus] = useState('idle') // idle | running | paused | done | stopped | revised | error
  const [activity, setActivity] = useState('连接后端中…')
  const [patient, setPatient] = useState({})
  const [steps, setSteps] = useState({})
  const [visitedNodes, setVisitedNodes] = useState([])
  const [currentNode, setCurrentNode] = useState(null)
  const [report, setReport] = useState([])
  const [trace, setTrace] = useState([])
  const [interrupt, setInterrupt] = useState(null)
  const [tab, setTab] = useState('report')

  const esRef = useRef(null)
  const tokenRef = useRef(0)
  const threadRef = useRef(null)
  const visitedRef = useRef(new Set())

  // 病例列表（挂载时拉取）
  useEffect(() => {
    let cancelled = false
    fetch('/api/cases')
      .then((r) => r.json())
      .then((list) => {
        if (cancelled) return
        setCases(list)
        setConn('connected')
        setActivity('就绪 — 选择病例后点击「开始诊断」')
      })
      .catch(() => {
        if (cancelled) return
        setConn('error')
        setActivity('无法连接后端，请先启动 server.py')
      })
    return () => { cancelled = true }
  }, [])

  const addVisited = useCallback((id) => {
    if (visitedRef.current.has(id)) return
    visitedRef.current.add(id)
    setVisitedNodes((prev) => [...prev, id])
  }, [])

  const resetAll = useCallback(() => {
    visitedRef.current = new Set()
    setVisitedNodes([])
    setCurrentNode(null)
    setPatient({})
    setSteps({})
    setReport([])
    setTrace([])
    setInterrupt(null)
  }, [])

  const appendTrace = useCallback((step) => {
    setTrace((prev) => [...prev, step])
  }, [])

  const endRun = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [])

  const animateChain = useCallback(
    async (chainPath) => {
      const token = tokenRef.current
      const visited = {}
      const traceByNode = {}
      chainPath.forEach((s) => {
        visited[s.node] = true
        if (!traceByNode[s.node]) traceByNode[s.node] = s
      })
      setTab('trace')
      for (const id of ORDER) {
        if (!visited[id] || visitedRef.current.has(id)) continue
        setCurrentNode(id)
        await sleep(300)
        if (token !== tokenRef.current) return
        addVisited(id)
        setCurrentNode(null)
        if (traceByNode[id]) appendTrace(traceByNode[id])
        await sleep(160)
        if (token !== tokenRef.current) return
      }
      setTab('report')
    },
    [addVisited, appendTrace],
  )

  const animateReport = useCallback(async (sections) => {
    const token = tokenRef.current
    for (const sec of sections) {
      setReport((prev) => [...prev, sec])
      await sleep(360)
      if (token !== tokenRef.current) return
    }
  }, [])

  const onNode = useCallback(
    (d) => {
      const name = d.name
      if (PIPE_LABEL[name]) {
        setSteps((prev) => ({ ...prev, [name]: 'done' }))
        if (name === 'check_red_lines') {
          setSteps((prev) => ({ ...prev, human_review: d.red_lines && d.red_lines.length ? 'active' : 'skipped' }))
        }
        setActivity('✓ ' + PIPE_LABEL[name])
      }
      if (d.patient) setPatient((prev) => ({ ...prev, name: d.patient.name }))
      if (d.features) {
        setPatient((prev) => ({ ...prev, gender: d.features.gender, age: d.features.age, diagnoses: d.features.diagnoses }))
      }
      if (d.subtype) {
        setPatient((prev) => ({ ...prev, subtype: d.subtype.subtype }))
        addVisited('A'); addVisited('B'); addVisited('C')
      }
      if (d.staging) {
        setPatient((prev) => ({ ...prev, staging: d.staging.current_tnm || d.staging.initial_tnm || d.staging.m_status }))
        addVisited('D')
      }
      if (name === 'trace_chain' && d.chain_path) animateChain(d.chain_path)
      else if (name === 'write_report' && d.report) animateReport(reportSections(d.report))
    },
    [addVisited, animateChain, animateReport],
  )

  const startRun = useCallback(
    (caseId) => {
      const token = ++tokenRef.current
      resetAll()
      setStatus('running')
      setActivity('启动流水线 …')
      const threadId = caseId + '-' + Date.now()
      threadRef.current = threadId

      const es = new EventSource(`/api/stream/${threadId}?case_id=${encodeURIComponent(caseId)}`)
      esRef.current = es

      es.addEventListener('status', (ev) => {
        const d = JSON.parse(ev.data)
        if (d.value === 'running') setStatus('running')
        else if (d.value === 'paused') setStatus('paused')
        else if (d.value === 'done') { setStatus('done'); setActivity('诊断完成 — 报告与决策链已生成'); endRun() }
        else if (d.value === 'stopped') { setStatus('stopped'); setActivity('已终止运行'); endRun() }
        else if (d.value === 'revised') { setStatus('revised'); setActivity('已标记待补充，请调整后重跑'); endRun() }
      })

      es.addEventListener('node', (ev) => {
        if (token !== tokenRef.current) return
        onNode(JSON.parse(ev.data))
      })
      es.addEventListener('interrupt', (ev) => {
        if (token !== tokenRef.current) return
        const d = JSON.parse(ev.data)
        setInterrupt(d)
        setStatus('paused')
      })
      es.addEventListener('run_error', (ev) => {
        let msg = '未知错误'
        try { msg = JSON.parse(ev.data).message || msg } catch (e) { /* ignore */ }
        setStatus('error')
        setActivity('运行出错：' + msg)
        endRun()
      })
      es.onerror = () => {
        if (esRef.current !== es) return // 已正常结束或被新运行取代
        esRef.current = null
        if (token === tokenRef.current) { setActivity('连接中断'); endRun() }
      }
    },
    [resetAll, onNode, endRun],
  )

  const resume = useCallback((decision) => {
    const tid = threadRef.current
    if (tid) {
      fetch(`/api/resume/${tid}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision }) }).catch(() => {})
    }
    setInterrupt(null)
  }, [])

  const stopRun = useCallback(() => {
    const tid = threadRef.current
    if (tid) fetch(`/api/stop/${tid}`, { method: 'POST' }).catch(() => {})
    endRun()
    setInterrupt(null)
    setStatus('stopped')
    setActivity('已终止当前运行')
  }, [endRun])

  return {
    cases, conn, status, activity, patient, steps, visitedNodes, currentNode,
    report, trace, interrupt, tab, setTab,
    startRun, stopRun, resume,
  }
}
