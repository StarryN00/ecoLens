"""T7 —— 操作手册(.docx)构建脚本。

用法
----
    python docs/manual/build_manual.py

产物:docs/manual/OPERATION_MANUAL.docx

设计
----
- 一章一个函数 ``chapter_NN_xxx(doc)``;``main()`` 顺序调用后保存。
- 章节里的截图放在 docs/manual/assets/,文件名见各章 ``screenshot()`` 调用。
  截图缺失时自动插入占位提示,**不影响构建** —— 这样可以先把骨架搭好、
  跑通,再由任务 S6 补图、S7 补正文。
- 复用后端的 docx_style.py:按文件路径 import(不走 app 包),避免触发
  app 包的副作用。docx_style 是纯 python-docx 模块,这样 import 是安全的。

本文件是 Opus 出的参考实现:脚手架 + 第 1 章已完整;第 2-9 章留了函数桩,
每个桩的 docstring 写明了该章要写什么 —— 任务 S7 照第 1 章的写法补全。
"""

from __future__ import annotations

import os
import sys

# —— 路径 ————————————————————————————————————————————————
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS_DIR = os.path.join(HERE, "assets")
OUTPUT = os.path.join(HERE, "OPERATION_MANUAL.docx")

# docx_style.py 是纯 python-docx 模块,直接按目录 import
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app", "services"))

import docx_style as S  # noqa: E402
from docx import Document  # noqa: E402

SYSTEM_NAME = "樟巢螟智能检测系统"


def screenshot(doc, filename, caption):
    """插入截图;文件不存在时插占位提示(任务 S6 补图后自动生效)。"""
    path = os.path.join(ASSETS_DIR, filename)
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            S.add_image_with_caption(doc, fh.read(), caption, width_inch=5.8)
    else:
        S.add_callout(
            doc,
            f"截图待补(任务 S6):assets/{filename} —— {caption}",
            kind="warn",
        )


# —— 第 1 章:登录系统(参考实现,完整)————————————————————————
def chapter_01_login(doc):
    S.add_heading(doc, "第 1 章　登录系统", level=1)
    S.add_body(
        doc,
        "樟巢螟智能检测系统是面向林业巡检的无人机影像识别工作台,"
        "用于上传航拍影像、自动识别樟巢螟虫巢并生成巡检报告。"
        "本手册介绍系统各功能的操作步骤,适用于巡检员与系统管理员。",
    )

    S.add_heading(doc, "1.1　打开系统", level=2)
    S.add_body(
        doc,
        "在浏览器中访问系统网址(由管理员提供),进入登录页。"
        "推荐使用 Chrome、Edge 等现代浏览器,以获得最佳显示效果。",
    )
    screenshot(doc, "01_login_page.png", "图 1-1　系统登录页")

    S.add_heading(doc, "1.2　登录步骤", level=2)
    S.add_bullets(
        doc,
        [
            "在「用户名」输入框中填写账号。",
            "在「密码」输入框中填写密码。",
            "点击「登录」按钮;验证通过后即进入巡检任务工作台。",
        ],
    )
    S.add_callout(
        doc,
        "若还没有账号,请联系系统管理员在「用户管理」页面创建;"
        "系统不开放管理员权限的自助注册。",
        kind="tip",
    )

    S.add_heading(doc, "1.3　退出登录", level=2)
    S.add_body(
        doc,
        "点击界面右上角的用户名展开下拉菜单,选择「退出登录」即可安全退出。"
        "在公用电脑上使用完毕后请务必退出登录。",
    )


# —— 第 2-9 章:函数桩 —— 任务 S7 照第 1 章样板补全 ————————————————
def chapter_02_roles(doc):
    """第 2 章 角色与权限 —— TODO(S7)。

    内容:说明「普通用户」与「系统管理员」的功能差异 ——
    普通用户可建任务 / 上传影像 / 看结果 / 导报告;管理员额外可进
    「区域管理」「用户管理」。权限边界写清楚。截图可选。
    """
    S.add_heading(doc, "第 2 章　角色与权限", level=1)
    S.add_body(doc, "（本章由任务 S7 实现）")


def chapter_03_region_admin(doc):
    """第 3 章 区域管理(管理员)—— TODO(S7)。

    内容:三级行政区域目录(市 / 区 / 街镇)的查看与增删改;
    强调巡检任务必须挂在街镇级。截图:区域管理页 + 新增弹窗。
    """
    S.add_heading(doc, "第 3 章　区域管理（管理员）", level=1)
    S.add_body(doc, "（本章由任务 S7 实现）")


def chapter_04_user_admin(doc):
    """第 4 章 用户管理(管理员)—— TODO(S7)。

    内容:创建用户、重置密码、启用/停用、设/撤管理员。
    截图:用户管理页 + 创建用户弹窗。
    """
    S.add_heading(doc, "第 4 章　用户管理（管理员）", level=1)
    S.add_body(doc, "（本章由任务 S7 实现）")


def chapter_05_create_task(doc):
    """第 5 章 新建巡检任务 —— TODO(S7)。

    内容:三级级联选择行政区域、填地块面积(亩)与林业局小班号、
    上传无人机影像。截图:新建任务表单 + 上传步骤。
    """
    S.add_heading(doc, "第 5 章　新建巡检任务", level=1)
    S.add_body(doc, "（本章由任务 S7 实现）")


def chapter_06_view_results(doc):
    """第 6 章 查看检测结果 —— TODO(S7)。

    内容:任务详情的「概览 / 虫巢地图 / 图片标注 / 虫巢清单」四个标签页;
    标注框颜色含义。截图:每个标签页各一张。
    """
    S.add_heading(doc, "第 6 章　查看检测结果", level=1)
    S.add_body(doc, "（本章由任务 S7 实现）")


def chapter_07_export_report(doc):
    """第 7 章 导出报告 —— TODO(S7)。

    内容:PDF / Excel / Word 三种格式的导出入口与差异说明
    (Word 报告即 T5 新增功能)。截图:报告导出按钮。
    """
    S.add_heading(doc, "第 7 章　导出报告", level=1)
    S.add_body(doc, "（本章由任务 S7 实现）")


def chapter_08_change_password(doc):
    """第 8 章 修改密码 —— TODO(S7)。

    内容:右上角菜单 -> 修改密码 -> 输入旧密码与新密码。
    截图:修改密码弹窗。
    """
    S.add_heading(doc, "第 8 章　修改密码", level=1)
    S.add_body(doc, "（本章由任务 S7 实现）")


def chapter_09_faq(doc):
    """第 9 章 常见问题与故障排查 —— TODO(S7)。

    内容:登录失败、上传失败、检测结果为空、图片加载慢等的排查建议。
    用 S.add_callout 标注每条提示。无需截图。
    """
    S.add_heading(doc, "第 9 章　常见问题与故障排查", level=1)
    S.add_body(doc, "（本章由任务 S7 实现）")


def main():
    doc = Document()
    S.setup_document(doc)
    S.add_cover(
        doc,
        title=SYSTEM_NAME,
        subtitle="操作手册",
        meta={"文档版本": "v1.0", "适用对象": "巡检员 / 系统管理员"},
    )

    chapter_01_login(doc)
    chapter_02_roles(doc)
    chapter_03_region_admin(doc)
    chapter_04_user_admin(doc)
    chapter_05_create_task(doc)
    chapter_06_view_results(doc)
    chapter_07_export_report(doc)
    chapter_08_change_password(doc)
    chapter_09_faq(doc)

    S.add_page_footer(doc, f"{SYSTEM_NAME} · 操作手册")

    doc.save(OUTPUT)
    print(f"OK: 已生成 {OUTPUT}")


if __name__ == "__main__":
    main()
