// utils/price.js
// 价格裁决（已确认）：
// - 活动价：activity 非空即视为活动生效
// - 可命中集合：original 永远可用；member/employee 需身份命中；activity 无需身份
// - 最终价：取可命中集合最低价；若并列按 activity > member > employee > original 选择来源
// - 规格：specs/health-services-platform/design.md（price 结构固化） + specs/health-services-platform/tasks.md（REQ-MP-P1-013）

function _isNumber(x) {
  return typeof x === 'number' && !Number.isNaN(x)
}

/**
 * @param {object} price
 * @param {string[]} identities e.g. ["MEMBER","EMPLOYEE"]
 */
function computeDisplayPrice(price, identities = []) {
  const p = price || {}
  const original = _isNumber(p.original) ? p.original : 0

  const ids = new Set((identities || []).map((x) => String(x || '').trim()).filter(Boolean))
  const activityOk = _isNumber(p.activity)
  const memberOk = ids.has('MEMBER') && _isNumber(p.member)
  const employeeOk = ids.has('EMPLOYEE') && _isNumber(p.employee)

  /** @type {{ type: 'activity'|'member'|'employee'|'original', value: number }[]} */
  const candidates = [{ type: 'original', value: original }]
  if (activityOk) candidates.push({ type: 'activity', value: p.activity })
  if (memberOk) candidates.push({ type: 'member', value: p.member })
  if (employeeOk) candidates.push({ type: 'employee', value: p.employee })

  // 取最低价；并列按 activity > member > employee > original
  const minValue = Math.min(...candidates.map((x) => Number(x.value || 0)))
  const tiedTypes = candidates.filter((x) => Number(x.value || 0) === minValue).map((x) => x.type)
  const priority = ['activity', 'member', 'employee', 'original']
  let priceType = 'original'
  for (const t of priority) {
    if (tiedTypes.includes(t)) {
      priceType = t
      break
    }
  }
  const displayPrice = minValue

  return {
    originalPrice: original,
    displayPrice,
    priceType,
    // 标签：按“可命中集合”回显
    hasActivityPrice: activityOk,
    hasMemberPrice: memberOk,
    hasEmployeePrice: employeeOk,
  }
}

module.exports = {
  computeDisplayPrice,
}
