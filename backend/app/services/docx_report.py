"""T5 —— 巡检任务 Word 报告生成。

入口:``build_task_report_docx(...) -> bytes``

该函数是**纯函数**:只接收已组装好的 dict / list,不碰数据库、不碰 ORM,
因此可在 tests/test_reports.py 里用假数据直接测,无需起 DB。

调用方(backend/app/api/reports.py —— 见分工方案任务 S3)负责:
  1. 鉴权 + ownership(``Depends(get_owned_task)``)
  2. 从 DB 把 task / results / nests / 标注图查出来,转成下面的 dict 结构
  3. 调 ``build_task_report_docx`` 拿 bytes,用 ``StreamingResponse`` 返回,
     media_type =
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

本文件是 Opus 出的参考实现:封面 + §1 已完整;§2/§3/§4 留了函数桩,
每个桩的 docstring 写明了规范 —— 任务 S2 照 §1 的写法补全即可。
所有样式只许调 docx_style 的助手,不要在这里写样式代码。
"""

from __future__ import annotations

import io
from datetime import datetime

from app.services import docx_style as S

SYSTEM_NAME = "樟巢螟智能检测系统"

_STATUS_CN = {
    "uploading": "上传中",
    "processing": "检测中",
    "completed": "已完成",
    "failed": "失败",
}
_SEVERITY_CN = {"severe": "重度", "medium": "中度", "light": "轻度"}


def build_task_report_docx(*, task, results, nests, annotated_images) -> bytes:
    """生成一份巡检任务 Word 报告,返回 .docx 的二进制内容。

    参数(全部是纯 Python 结构,不是 ORM 对象):
      task: dict —— 键:
        task_name, region_path, area_name, operator, plot_area_mu,
        forestry_sub_compartment, status, created_at(datetime|None),
        completed_at(datetime|None), total_images(int), processed_images(int)
      results: dict|None —— /api/v1/tasks/{id}/results 的返回体
        {"image_stats": {...}, "nest_stats": {...}};任务无结果时传 None
      nests: list[dict] —— 每项键:
        nest_code, longitude, latitude, severity, confidence, detection_count
      annotated_images: list[tuple[bytes, str]] —— [(JPEG字节, 图注), ...]
    """
    from docx import Document

    doc = Document()
    S.setup_document(doc)

    _section_cover(doc, task)
    _section_basic_info(doc, task)
    _section_statistics(doc, results)
    _section_nest_list(doc, nests)
    _section_annotated_images(doc, annotated_images)

    S.add_page_footer(doc, f"{SYSTEM_NAME} · 巡检报告")

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# —— 封面(参考实现,完整)————————————————————————————————
def _section_cover(doc, task):
    S.add_cover(
        doc,
        title=SYSTEM_NAME,
        subtitle="巡检检测报告",
        meta={
            "任务名称": task.get("task_name") or "—",
            "所属区域": task.get("region_path") or "未分配",
            "生成时间": _fmt_dt(datetime.now()),
        },
    )


# —— §1 任务基本信息(参考实现,完整)————————————————————————
def _section_basic_info(doc, task):
    S.add_heading(doc, "一、任务基本信息", level=1)
    rows = [
        ("任务名称", task.get("task_name") or "—"),
        ("所属区域", task.get("region_path") or "未分配"),
        ("巡检区域说明", task.get("area_name") or "—"),
        ("操作员", task.get("operator") or "—"),
        ("地块面积", _fmt_area(task.get("plot_area_mu"))),
        ("林业局小班号", task.get("forestry_sub_compartment") or "—"),
        ("任务状态", _STATUS_CN.get(task.get("status"), task.get("status") or "—")),
        ("创建时间", _fmt_dt(task.get("created_at"))),
        ("完成时间", _fmt_dt(task.get("completed_at"))),
        (
            "影像数量",
            f"{task.get('total_images') or 0} 张"
            f"(已处理 {task.get('processed_images') or 0} 张)",
        ),
    ]
    S.add_kv_table(doc, rows)


# —— §2 检测统计(函数桩 —— 任务 S2 补全)——————————————————————
def _section_statistics(doc, results):
    """§2 检测统计 —— TODO(S2)。

    规范:
    - ``S.add_heading(doc, "二、检测统计", level=1)``
    - results 为 None:``S.add_body(doc, "该任务暂无检测结果。")`` 后 return。
    - 否则两张 ``S.add_data_table``:
        影像统计:表头 ["处理图片数", "含香樟树", "含虫巢", "虫巢检测总数"],
          一行数据取 ``results["image_stats"]`` 的 total_processed /
          with_camphor_tree / with_nests / total_nest_detections。
        虫巢统计:表头 ["去重后虫巢", "重度", "中度", "轻度"],
          一行数据取 ``results["nest_stats"]`` 的
          total_unique / severe / medium / light。
      两张表之间可 ``S.add_body`` 一句小标题或留空。
    """
    S.add_heading(doc, "二、检测统计", level=1)
    S.add_body(doc, "（本节由任务 S2 实现）")


# —— §3 虫巢清单(函数桩 —— 任务 S2 补全)——————————————————————
def _section_nest_list(doc, nests):
    """§3 虫巢清单 —— TODO(S2)。

    规范:
    - ``S.add_heading(doc, "三、虫巢清单", level=1)``
    - nests 为空:``S.add_body(doc, "未发现虫巢。")`` 后 return。
    - 否则 ``S.add_data_table``,表头
      ["编号", "虫巢编码", "经度", "纬度", "严重度", "置信度", "检出次数"]:
        编号 = 行序号(从 1 起)
        经度/纬度 = 保留 6 位小数(用 ``f"{v:.6f}"``,None 显示 "—")
        严重度 = ``_SEVERITY_CN.get(severity, severity)``
        置信度 = 百分比(如 0.87 -> "87%";None 显示 "—")
        检出次数 = detection_count
    """
    S.add_heading(doc, "三、虫巢清单", level=1)
    S.add_body(doc, "（本节由任务 S2 实现）")


# —— §4 标注影像附录(函数桩 —— 任务 S2 补全)————————————————————
def _section_annotated_images(doc, annotated_images):
    """§4 标注影像附录 —— TODO(S2)。

    规范:
    - ``S.add_heading(doc, "四、标注影像附录", level=1)``
    - annotated_images 为空:``S.add_body(doc, "无标注影像。")`` 后 return。
    - 否则对每个 ``(jpeg_bytes, caption)`` 调
      ``S.add_image_with_caption(doc, jpeg_bytes, caption, width_inch=5.8)``。
    """
    S.add_heading(doc, "四、标注影像附录", level=1)
    S.add_body(doc, "（本节由任务 S2 实现）")


# —— 小工具 ————————————————————————————————————————————————
def _fmt_dt(value):
    """datetime -> 'YYYY-MM-DD HH:MM';空值 -> '—'。"""
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _fmt_area(value):
    """地块面积 -> 'N 亩';空值 -> '—'。"""
    if value is None:
        return "—"
    return f"{value:g} 亩"
