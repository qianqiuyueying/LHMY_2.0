# 审计覆盖率（v1）验收记录

- 时间窗：近 7 天（since `2025-12-16T04:00:06.149716+00:00`）
- 覆盖判定：每类 `resourceType` 计数 ≥ 1 即覆盖
- 覆盖率：1/6 = 16.7%

## 1. 分母（高风险事件清单）
- `EXPORT_DEALER_ORDERS`
- `DEALER_SETTLEMENT_BATCH`
- `DEALER_SETTLEMENT`
- `ORDER`
- `DEALER_LINK`
- `BOOKING`

## 2. 统计结果

| resourceType | count | covered |
|---|---:|---|
| `EXPORT_DEALER_ORDERS` | 1 | YES |
| `DEALER_SETTLEMENT_BATCH` | 0 | NO |
| `DEALER_SETTLEMENT` | 0 | NO |
| `ORDER` | 0 | NO |
| `DEALER_LINK` | 0 | NO |
| `BOOKING` | 0 | NO |

## 3. 未覆盖清单（需阻断上线/回归）
- `DEALER_SETTLEMENT_BATCH`
- `DEALER_SETTLEMENT`
- `ORDER`
- `DEALER_LINK`
- `BOOKING`

## 4. 备注
- 本记录由脚本自动生成；如需更严格阈值（按天/按环境），需另行拍板升级规格。
