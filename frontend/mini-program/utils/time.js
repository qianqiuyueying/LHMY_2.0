// utils/time.js
// 用户端时间展示：按设备本地时区显示（你已拍板）

function pad2(n) {
  const x = Number(n || 0)
  return x < 10 ? `0${x}` : String(x)
}

function formatLocalDateTime(iso) {
  const s = String(iso || '').trim()
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

module.exports = {
  formatLocalDateTime
}


