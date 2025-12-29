import sys
from pathlib import Path

# pytest 运行时 sys.path 可能不包含仓库根目录；显式补齐以便导入 scripts/ 下的验收脚本
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.audit_coverage_report import REQUIRED_RESOURCE_TYPES, _render_markdown  # noqa: E402


def test_render_markdown_contains_all_required_resource_types() -> None:
    counts = {REQUIRED_RESOURCE_TYPES[0]: 3, REQUIRED_RESOURCE_TYPES[3]: 1}
    md = _render_markdown(days=7, since_iso="2025-12-23T00:00:00+00:00", counts=counts)
    for rt in REQUIRED_RESOURCE_TYPES:
        assert f"`{rt}`" in md


def test_render_markdown_marks_missing_as_no() -> None:
    md = _render_markdown(days=7, since_iso="2025-12-23T00:00:00+00:00", counts={})
    # 任意一个资源类型都应显示为 NO（count=0）
    assert "| `EXPORT_DEALER_ORDERS` | 0 | NO |" in md


