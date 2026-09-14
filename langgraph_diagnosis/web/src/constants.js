// LangGraph 流水线节点（与后端 nodes.py 的节点名一一对应）
export const PIPE = [
  ['load_patient', '读取病历'],
  ['extract_features', '抽取特征'],
  ['retrieve_guide', '检索指南'],
  ['judge_subtype', '分子分型'],
  ['judge_staging', 'TNM分期'],
  ['check_red_lines', '红线检查'],
  ['human_review', '红线复核'],
  ['trace_chain', '决策链回溯'],
  ['write_report', '生成报告'],
  ['human_approve', '报告终审'],
]

export const PIPE_LABEL = Object.fromEntries(PIPE)
