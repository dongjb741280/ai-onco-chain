import { esc } from '../render'

// interrupt.type === 'red_line_review' | 'report_approval'
export default function ReviewModal({ interrupt, onResume }) {
  if (!interrupt) return null
  const isRedLine = interrupt.type === 'red_line_review'

  return (
    <div className="overlay open">
      <div className="modal">
        {isRedLine ? (
          <>
            <h3>⚠ 命中安全红线</h3>
            <p className="mdesc">以下红线需人工复核后再决定是否继续：</p>
            {(interrupt.red_lines || []).map((l, i) => (
              <div key={i} className="redline-item">
                <div className="rk">{esc(l.kind)}</div>
                <div className="rd">{esc(l.description)}</div>
                <div className="ra">建议：{esc(l.action)}</div>
              </div>
            ))}
            <div className="modal-actions">
              <button className="primary" onClick={() => onResume('proceed')}>继续（已人工评估）</button>
              <button className="danger" onClick={() => onResume('stop')}>终止</button>
              <button onClick={() => onResume('revise')}>补充后重跑</button>
            </div>
          </>
        ) : (
          <>
            <h3>✓ 报告终审</h3>
            <p className="mdesc">诊断报告与决策链已生成，请复核后确认。</p>
            <div className="modal-actions">
              <button className="primary" onClick={() => onResume('approve')}>通过</button>
              <button onClick={() => onResume('revise')}>返回修改</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
