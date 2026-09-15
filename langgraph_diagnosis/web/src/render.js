// 报告 / 追踪的渲染辅助：把后端的 markdown 表格字段转成 HTML

export function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
}

export function inline(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]*P\s*(\d+)[^\]]*)\]/g, (m, text, page) => `<span class="cite" data-page="${page}">${text}</span>`)
}

// 指南原文的轻量 markdown 渲染（去 HTML 注释，支持标题/表格/段落）
export function renderSource(text) {
  const clean = String(text || '').replace(/<!--[\s\S]*?-->/g, '')
  const lines = clean.split('\n')
  let html = ''
  let i = 0
  while (i < lines.length) {
    const t = lines[i].trim()
    if (!t) { i++; continue }
    if (t.startsWith('|')) {
      const block = []
      while (i < lines.length && lines[i].trim().startsWith('|')) { block.push(lines[i]); i++ }
      html += mdTable(block.join('\n'))
    } else if (/^#{1,3}\s/.test(t)) {
      const m = t.match(/^(#{1,3})\s+(.*)$/)
      html += `<h${m[1].length} class="src-h">${inline(m[2])}</h${m[1].length}>`
      i++
    } else {
      html += `<p class="src-p">${inline(t)}</p>`
      i++
    }
  }
  return html || '<p class="empty">（无内容）</p>'
}

export function mdTable(text) {
  if (!text) return '<p class="empty">（无）</p>'
  const lines = String(text).trim().split('\n').filter((l) => l.trim().indexOf('|') === 0)
  if (lines.length < 2) return '<p>' + inline(text) + '</p>'
  const rows = lines.map((l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim()))
  const header = rows[0]
  const body = rows.slice(2)
  let html = '<table class="rpt-table"><thead><tr>' + header.map((h) => `<th>${inline(h)}</th>`).join('') + '</tr></thead><tbody>'
  body.forEach((r) => { html += '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>' })
  return html + '</tbody></table>'
}

export function rptList(items) {
  if (!items || !items.length) return '<p class="empty">（无）</p>'
  return '<ul>' + items.map((i) => `<li>${inline(i)}</li>`).join('') + '</ul>'
}

// 把后端 DiagnosisReport 映射成前端分节展示
export function reportSections(report) {
  return [
    { title: '主要诊断', html: '<p>' + (report.main_diagnosis || []).map((d) => esc(d)).join('<br>') + '</p>' },
    { title: '病理与分子分型', html: mdTable(report.molecular_table) },
    { title: 'TNM 分期', html: '<p>' + esc(report.tnm_staging) + '</p>' },
    { title: '诊疗经过', html: mdTable(report.treatment_timeline) },
    { title: '治疗评价（对照指南）', html: mdTable(report.treatment_evaluation) },
    { title: '后续建议', html: rptList(report.recommendations) },
    { title: '卡点 / 待核实', html: rptList(report.blockers) },
  ]
}
