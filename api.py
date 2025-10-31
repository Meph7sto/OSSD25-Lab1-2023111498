# -*- coding: utf-8 -*-
"""
项目上下文打包器 (Tkinter)
------------------------------------------------------------
- 稳定方案：用“目录图标法”实现大号展开/折叠按钮（不改 ttk 内部布局，避免 Windows Tk 报错）
- 左键单击：勾选/取消勾选（含三态）
- 右键文件夹：展开/折叠（亦支持 Ctrl+左键）111111111111111
- 禁止双击展开（防止“快速双击栏目”误展开）
- 生成后统计：行数、字符、词数、估算 Token2222222222222222222222222222
- 可选：在输出顶部生成仅选中项/所有文件的文件树
- 取消蓝色选中高亮（selectmode="none"）
- 斑马纹分割效果（增强每行“分隔感”）
- 无第三方依赖
"""

import os
import sys
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ----------------------------- 可调参数 ----------------------------- #

ICON_SIZE = 18  # 目录图标（+/-）大小：18/20/22/24 均可
TREE_FONT = ("TkDefaultFont", 11)
ROW_HEIGHT = max(24, ICON_SIZE + 8)

# 斑马纹颜色（增强分割感）
ROW_BG_EVEN = "#FFFFFF"
ROW_BG_ODD  = "#F2F2F2"

# ----------------------------- 实用常量 ----------------------------- #

IGNORED_DIRS = {
    "__pycache__", ".git", ".vscode", "node_modules", ".DS_Store", ".idea",
    "dist", "build", "target", ".svn", ".hg", ".tox", ".mypy_cache",
    ".pytest_cache", "venv", ".venv", "env", ".env", ".terraform"
}

IGNORED_FILES = {".DS_Store", "Thumbs.db"}

# 常见二进制扩展名（可按需增补）
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
    ".pdf",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".lz",
    ".mp3", ".wav", ".flac", ".ogg", ".m4a",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".class", ".pyc", ".pyo", ".o", ".a", ".lib",
    ".ttf", ".otf", ".woff", ".woff2",
    ".psd", ".ai", ".sketch", ".blend",
    ".obj", ".stl", ".glb", ".fbx"
}

# 复选框字符：未选/已选/部分选（更大更清晰）
CHECKBOX = {0: "☐", 1: "☑", 2: "◪"}


# ----------------------------- 主应用 ----------------------------- #

class FileContextPackager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("项目上下文打包器 (Tkinter)")
        self.geometry("1100x720")
        self.minsize(900, 560)

        # 状态数据
        self.project_root = None
        self.item_state = {}         # item_id -> 0/1/2
        self.item_path = {}          # item_id -> 绝对路径
        self.item_is_dir = {}        # item_id -> bool
        self.item_is_binary = {}     # item_id -> bool (仅文件)
        self._building_tree = False
        self.root_iid = None

        # 统计栏变量
        self.stats_var = tk.StringVar(value="行:0  字符(含空格):0  字符(不含空格):0  词:0  估算Token:0")
        # 顶部输出：仅选中项 / 所有文件
        self.include_tree_selected_var = tk.BooleanVar(value=False)
        self.include_tree_all_var = tk.BooleanVar(value=False)

        # 图像引用（防止被回收）
        self._img_indicator_closed = None  # 目录合拢(+)
        self._img_indicator_open = None    # 目录展开(-)
        self._img_file = None              # 文件占位图标

        # 全局样式（字体、行高）
        self.style = ttk.Style(self)
        self.style.configure("Treeview", rowheight=ROW_HEIGHT, font=TREE_FONT)
        self.style.configure("Treeview.Heading", font=("TkDefaultFont", 11, "bold"))

        # 斑马纹标签样式
        self.tree_tag_even = "row_even"
        self.tree_tag_odd  = "row_odd"

        # 创建自绘的大号 + / - 图标（目录图标法，跨平台稳定）
        self._make_dir_icons(size=ICON_SIZE)

        self._build_ui()

    # ------------------------- 颜色解析与绘图 ------------------------- #
    def _resolve_color(self, color_name, default="#FFFFFF"):
        """将 Tk 颜色（含 System*）转换为 #RRGGBB。"""
        try:
            r, g, b = self.winfo_rgb(color_name)  # 0..65535
            return f"#{r // 256:02x}{g // 256:02x}{b // 256:02x}"
        except tk.TclError:
            return default

    def _make_dir_icons(self, size=18):
        """生成两张目录图标：合拢(+) 与 展开(-)，再生成一个文件占位点。"""
        bg = self.style.lookup("Treeview", "background") or "#FFFFFF"
        bg_hex = self._resolve_color(bg, "#FFFFFF")

        def draw_box_icon(plus=True):
            s = size
            pad = max(2, s // 9)         # 外边距
            bw = max(1, s // 14)         # 边框粗细
            lw = max(2, s // 6)          # 横/竖线粗细
            img = tk.PhotoImage(width=s, height=s)
            # 背景
            img.put(bg_hex, to=(0, 0, s, s))
            # 边框（深灰）
            border = "#6b6b6b"
            for i in range(bw):
                img.put(border, to=(pad + i, pad + i, s - pad - i, pad + i + 1))                # 上
                img.put(border, to=(pad + i, s - pad - i - 1, s - pad - i, s - pad - i))        # 下
                img.put(border, to=(pad + i, pad + i, pad + i + 1, s - pad - i))                # 左
                img.put(border, to=(s - pad - i - 1, pad + i, s - pad - i, s - pad - i))        # 右
            # 中线（减号）
            cx = s // 2
            cy = s // 2
            half = max(3, s // 3)
            img.put(border, to=(cx - half, cy - lw // 2, cx + half + 1, cy + (lw + 1) // 2))
            if plus:
                # 竖线（加号）
                img.put(border, to=(cx - lw // 2, cy - half, cx + (lw + 1) // 2, cy + half + 1))
            return img

        def draw_dot_icon():
            s = max(10, size // 2)
            img = tk.PhotoImage(width=s, height=s)
            bg_hex_loc = self._resolve_color(self.style.lookup("Treeview", "background") or "#FFFFFF", "#FFFFFF")
            img.put(bg_hex_loc, to=(0, 0, s, s))
            # 小方点
            dot = "#6b6b6b"
            m = max(2, s // 4)
            img.put(dot, to=(m, m, s - m, s - m))
            return img

        self._img_indicator_closed = draw_box_icon(plus=True)   # 未展开（+）
        self._img_indicator_open  = draw_box_icon(plus=False)   # 已展开（−）
        self._img_file = draw_dot_icon()

    # ------------------------- UI 构建 ------------------------- #

    def _build_ui(self):
        # 顶部：选择根目录
        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=8, pady=6)

        btn_choose = ttk.Button(top, text="选择项目根目录", command=self.choose_root)
        btn_choose.pack(side="left")

        self.lbl_root = ttk.Label(top, text="未选择", width=80)
        self.lbl_root.pack(side="left", padx=10)

        # 中间：左右分栏
        mid = ttk.Panedwindow(self, orient="horizontal")
        mid.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # 左侧：Treeview（selectmode="none" 取消蓝色选中高亮）
        left = ttk.Frame(mid)
        self.tree = ttk.Treeview(left, show="tree", selectmode="none")
        vsb_tree = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        hsb_tree = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb_tree.set, xscrollcommand=hsb_tree.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb_tree.grid(row=0, column=1, sticky="ns")
        hsb_tree.grid(row=1, column=0, sticky="ew")

        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        mid.add(left, weight=1)

        # 右侧：Text 输出
        right = ttk.Frame(mid)
        self.txt = tk.Text(right, wrap="none", undo=False)
        vsb_text = ttk.Scrollbar(right, orient="vertical", command=self.txt.yview)
        hsb_text = ttk.Scrollbar(right, orient="horizontal", command=self.txt.xview)
        self.txt.configure(yscrollcommand=vsb_text.set, xscrollcommand=hsb_text.set)

        self.txt.grid(row=0, column=0, sticky="nsew")
        vsb_text.grid(row=0, column=1, sticky="ns")
        hsb_text.grid(row=1, column=0, sticky="ew")

        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        mid.add(right, weight=1)

        # 底部：按钮 + 选项 + 状态
        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", padx=8, pady=6)

        btn_select_all = ttk.Button(bottom, text="全选", command=self.select_all)
        btn_unselect_all = ttk.Button(bottom, text="全不选", command=self.unselect_all)
        btn_gen = ttk.Button(bottom, text="生成上下文", command=self.generate_context)
        btn_copy = ttk.Button(bottom, text="复制到剪贴板", command=self.copy_to_clipboard)

        btn_select_all.pack(side="left")
        btn_unselect_all.pack(side="left", padx=(6, 12))
        btn_gen.pack(side="left")
        btn_copy.pack(side="left", padx=8)

        # 选项：顶部输出文件树（两种）
        chk_tree_sel = ttk.Checkbutton(bottom, text="顶部输出文件树（仅含选中项）", variable=self.include_tree_selected_var)
        chk_tree_all = ttk.Checkbutton(bottom, text="顶部输出文件树（项目所有文件）", variable=self.include_tree_all_var)
        chk_tree_sel.pack(side="left", padx=12)
        chk_tree_all.pack(side="left", padx=6)

        # 统计栏（右侧）
        lbl_stats = ttk.Label(bottom, textvariable=self.stats_var, anchor="e")
        lbl_stats.pack(side="right")

        # Treeview 标签样式
        self.tree.tag_configure("disabled", foreground="#9a9a9a")
        self.tree.tag_configure("dir", font=("TkDefaultFont", 11, "bold"))
        self.tree.tag_configure(self.tree_tag_even, background=ROW_BG_EVEN)
        self.tree.tag_configure(self.tree_tag_odd,  background=ROW_BG_ODD)

        # 左键：切换勾选；空格键也可切换当前行
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<space>", self.on_space_toggle)
        # 右键：展开/折叠目录（mac 兼容 Ctrl+左键）
        self.tree.bind("<Button-3>", self.on_right_click_toggle_open)
        self.tree.bind("<Control-Button-1>", self.on_right_click_toggle_open)

        # 禁止双击展开
        self.tree.bind("<Double-1>", lambda e: "break")

        # 展开/收起时，同步目录图标
        self.tree.bind("<<TreeviewOpen>>", lambda e: self._sync_dir_icons())
        self.tree.bind("<<TreeviewClose>>", lambda e: self._sync_dir_icons())

    # ------------------------- 目录扫描/树构建 ------------------------- #

    def choose_root(self):
        path = filedialog.askdirectory()
        if not path:
            return
        self.project_root = os.path.abspath(path)
        self.lbl_root.config(text=self.project_root)

        # 清空当前树与状态
        for child in self.tree.get_children():
            self.tree.delete(child)
        self.item_state.clear()
        self.item_path.clear()
        self.item_is_dir.clear()
        self.item_is_binary.clear()
        self.root_iid = None

        # 构建新树
        self._building_tree = True
        try:
            display_name = os.path.basename(self.project_root) or self.project_root
            root_text = f"{CHECKBOX[0]}  {display_name}"
            # 根节点使用目录图标（默认打开）
            self.root_iid = self.tree.insert(
                "", "end", text=root_text, open=True, tags=("dir",), image=self._img_indicator_open
            )
            self._register_item(self.root_iid, self.project_root, is_dir=True, is_binary=False, state=0)
            self._populate_dir(self.root_iid, self.project_root)
        finally:
            self._building_tree = False

        # 斑马纹着色
        self._apply_row_stripes()

        # 清空输出与统计 + 同步一次图标
        self.txt.delete("1.0", "end")
        self._update_stats("")
        self._sync_dir_icons()

    def _register_item(self, iid, path, is_dir, is_binary, state=0):
        self.item_path[iid] = path
        self.item_is_dir[iid] = is_dir
        self.item_is_binary[iid] = is_binary
        self.item_state[iid] = state
        # 二进制文件置灰
        if is_binary and not is_dir:
            tags = set(self.tree.item(iid, "tags"))
            tags.add("disabled")
            self.tree.item(iid, tags=tuple(tags))

    def _populate_dir(self, parent_id, dir_path):
        try:
            entries = sorted(os.listdir(dir_path))
        except Exception:
            return

        dirs, files = [], []
        for name in entries:
            if name in IGNORED_FILES:
                continue
            full = os.path.join(dir_path, name)
            if os.path.isdir(full):
                if name in IGNORED_DIRS or os.path.islink(full):
                    continue
                dirs.append((name, full))
            else:
                files.append((name, full))

        # 先目录再文件
        for name, full in dirs:
            iid = self.tree.insert(
                parent_id, "end", text=f"{CHECKBOX[0]}  {name}", open=False, tags=("dir",),
                image=self._img_indicator_closed
            )
            self._register_item(iid, full, is_dir=True, is_binary=False, state=0)
            self._populate_dir(iid, full)

        for name, full in files:
            ext = os.path.splitext(name)[1].lower()
            is_bin = ext in BINARY_EXTS
            label = f"{CHECKBOX[0]}  {name}" + ("  (binary)" if is_bin else "")
            tags = ("disabled",) if is_bin else ()
            iid = self.tree.insert(parent_id, "end", text=label, open=False, tags=tags, image=self._img_file)
            self._register_item(iid, full, is_dir=False, is_binary=is_bin, state=0)

    # ------------------------- 目录图标同步 ------------------------- #

    def _sync_dir_icons(self):
        """根据每个目录项的 open 状态，切换 image 为 + / -"""
        for iid, is_dir in self.item_is_dir.items():
            if not is_dir:
                continue
            is_open = bool(self.tree.item(iid, "open"))
            self.tree.item(iid, image=(self._img_indicator_open if is_open else self._img_indicator_closed))

    # ------------------------- 行分隔效果（斑马纹） ------------------------- #

    def _apply_row_stripes(self):
        """为每个同级子节点交替设置背景，增强“分隔感”（跨平台稳定）。"""
        def stripe_children(parent):
            children = self.tree.get_children(parent)
            for idx, child in enumerate(children):
                # 清除旧条纹标签
                tags = set(self.tree.item(child, "tags"))
                tags.discard(self.tree_tag_even)
                tags.discard(self.tree_tag_odd)
                # 交替着色
                tags.add(self.tree_tag_even if idx % 2 == 0 else self.tree_tag_odd)
                self.tree.item(child, tags=tuple(tags))
                # 递归到下一层
                stripe_children(child)

        # 根层
        stripe_children("")
        # 根节点也着色一下（放在偶数色）
        if self.root_iid:
            tags = set(self.tree.item(self.root_iid, "tags"))
            tags.add(self.tree_tag_even)
            self.tree.item(self.root_iid, tags=tuple(tags))

    # ------------------------- 复选框逻辑 ------------------------- #

    def on_space_toggle(self, event):
        focus = self.tree.focus()
        if focus:
            self._toggle_item(focus)
            return "break"

    def on_tree_click(self, event):
        if self._building_tree:
            return

        row_iid = self.tree.identify_row(event.y)
        if not row_iid:
            return

        # 确保焦点在当前行（selectmode=none 不会出现蓝色选中，但仍有焦点）
        self.tree.focus(row_iid)

        elem = self.tree.identify_element(event.x, event.y)
        # 避免点击默认小三角指示器时也触发勾选
        if elem == "Treeitem.indicator":
            return

        region = self.tree.identify("region", event.x, event.y)
        if region != "tree":
            return

        # 左键单击：切换勾选
        self._toggle_item(row_iid)

    def on_right_click_toggle_open(self, event):
        """右键（或 Ctrl+左键）在目录上展开/收起"""
        row_iid = self.tree.identify_row(event.y)
        if not row_iid:
            return
        if not self.item_is_dir.get(row_iid, False):
            return
        # 切换 open 状态
        is_open = bool(self.tree.item(row_iid, "open"))
        self.tree.item(row_iid, open=not is_open)
        self._sync_dir_icons()

    def _toggle_item(self, iid):
        # 二进制文件不可勾选
        if self.item_is_binary.get(iid, False):
            return

        current = self.item_state.get(iid, 0)
        # 对于部分选中(2)，点击视为选中(1)
        new_state = 0 if current == 1 else 1
        self._set_state_recursive(iid, new_state)
        self._update_ancestors(iid)

    def _set_state_recursive(self, iid, state):
        """设置自身为 state，并向下递归（跳过不可勾选的二进制文件）。"""
        if self.item_is_binary.get(iid, False):
            return
        self.item_state[iid] = state
        self._refresh_label(iid)

        for child in self.tree.get_children(iid):
            self._set_state_recursive(child, state)

    def _update_ancestors(self, iid):
        """自底向上更新父节点三态。"""
        parent = self.tree.parent(iid)
        while parent:
            states = []
            for child in self.tree.get_children(parent):
                if self.item_is_binary.get(child, False):
                    continue
                states.append(self.item_state.get(child, 0))

            if not states:
                parent_state = 0  # 没有可选子项
            elif all(s == 1 for s in states):
                parent_state = 1
            elif all(s == 0 for s in states):
                parent_state = 0
            else:
                parent_state = 2  # 部分选中

            self.item_state[parent] = parent_state
            self._refresh_label(parent)
            parent = self.tree.parent(parent)

    def _refresh_label(self, iid):
        path = self.item_path[iid]
        is_dir = self.item_is_dir[iid]
        is_bin = self.item_is_binary[iid]
        name = os.path.basename(path) or path
        glyph = CHECKBOX[self.item_state.get(iid, 0)]
        text = f"{glyph}  {name}"
        if (not is_dir) and is_bin:
            text += "  (binary)"
        self.tree.item(iid, text=text)

    # ------------------------- 全选 / 全不选 ------------------------- #

    def select_all(self):
        """一键全选（跳过二进制文件）"""
        if not self.root_iid:
            messagebox.showinfo("提示", "请先选择项目根目录。")
            return
        self._set_state_recursive(self.root_iid, 1)

    def unselect_all(self):
        """一键全不选"""
        if not self.root_iid:
            messagebox.showinfo("提示", "请先选择项目根目录。")
            return
        self._set_state_recursive(self.root_iid, 0)

    # ------------------------- 文件树（选中项 / 全部） ------------------------- #

    def _has_selected_descendant(self, iid):
        """判断该节点是否‘有效选中’：文件被选中，或目录下存在被选中的后代。"""
        if not self.item_is_dir.get(iid, False):
            return self.item_state.get(iid, 0) == 1 and not self.item_is_binary.get(iid, False)

        for child in self.tree.get_children(iid):
            if self._has_selected_descendant(child):
                return True
        return False

    def _build_selected_tree_lines(self, iid, prefix="", is_last=True):
        """构造“仅包含选中项”的 ASCII 文件树行列表。"""
        lines = []
        if iid != self.root_iid:
            name = os.path.basename(self.item_path[iid]) or self.item_path[iid]
            state = self.item_state.get(iid, 0)
            mark = CHECKBOX[state]
            branch = "└── " if is_last else "├── "
            extra = " (binary)" if (not self.item_is_dir.get(iid, False) and self.item_is_binary.get(iid, False)) else ""
            lines.append(prefix + branch + f"{mark} {name}{extra}")

        children = [c for c in self.tree.get_children(iid) if self._has_selected_descendant(c)]
        for idx, child in enumerate(children):
            last = (idx == len(children) - 1)
            new_prefix = prefix + ("    " if is_last else "│   ") if iid != self.root_iid else ""
            lines.extend(self._build_selected_tree_lines(child, new_prefix, last))
        return lines

    def _build_full_tree_lines(self, iid, prefix="", is_last=True):
        """构造“包含所有条目”的 ASCII 文件树行列表。"""
        lines = []
        if iid != self.root_iid:
            name = os.path.basename(self.item_path[iid]) or self.item_path[iid]
            state = self.item_state.get(iid, 0)
            mark = CHECKBOX[state]
            branch = "└── " if is_last else "├── "
            extra = " (binary)" if (not self.item_is_dir.get(iid, False) and self.item_is_binary.get(iid, False)) else ""
            lines.append(prefix + branch + f"{mark} {name}{extra}")

        children = list(self.tree.get_children(iid))
        for idx, child in enumerate(children):
            last = (idx == len(children) - 1)
            new_prefix = prefix + ("    " if is_last else "│   ") if iid != self.root_iid else ""
            lines.extend(self._build_full_tree_lines(child, new_prefix, last))
        return lines

    # ------------------------- 统计 ------------------------- #

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        粗略 Token 估算：
        - CJK 字符：≈1 token
        - 其他：≈4 个字符 1 token
        """
        cjk = re.findall(r"[\u3400-\u4DBF\u4E00-\u9FFF\U00020000-\U0002CEAF\U0002CEB0-\U0002EBEF]", text)
        cjk_count = len(cjk)
        non_cjk_text = re.sub(r"[\u3400-\u4DBF\u4E00-\u9FFF\U00020000-\U0002CEAF\U0002CEB0-\U0002EBEF]", "", text)
        approx = cjk_count + (len(non_cjk_text) // 4)
        return int(approx)

    def _update_stats(self, text: str):
        lines = text.count("\n") + (1 if text else 0)
        chars_all = len(text)
        chars_nospace = len([c for c in text if not c.isspace()])
        words = len(re.findall(r"\S+", text))
        tokens = self._estimate_tokens(text)
        self.stats_var.set(
            f"行:{lines}  字符(含空格):{chars_all}  字符(不含空格):{chars_nospace}  词:{words}  估算Token:{tokens}"
        )

    # ------------------------- 生成上下文/复制 ------------------------- #

    def generate_context(self):
        if not self.project_root:
            messagebox.showinfo("提示", "请先选择项目根目录。")
            return

        blocks = []

        # 顶部：项目所有文件树（可选）
        if self.include_tree_all_var.get() and self.root_iid:
            all_lines = self._build_full_tree_lines(self.root_iid, prefix="", is_last=True)
            all_text = "### 文件树（项目所有文件）\n\n```\n" + "\n".join(all_lines) + "\n```\n"
            blocks.append(all_text)

        # 顶部：仅选中项文件树（可选）
        if self.include_tree_selected_var.get() and self.root_iid:
            sel_lines = self._build_selected_tree_lines(self.root_iid, prefix="", is_last=True)
            sel_text = "### 文件树（仅包含选中的条目）\n\n```\n" + "\n".join(sel_lines) + "\n```\n"
            blocks.append(sel_text)

        # 遍历所有“被选中的文件项”
        for iid, path in self.item_path.items():
            if self.item_is_dir.get(iid, False):
                continue
            if self.item_is_binary.get(iid, False):
                continue
            if self.item_state.get(iid, 0) != 1:
                continue

            try:
                rel = os.path.relpath(path, self.project_root)
            except ValueError:
                rel = path  # 跨盘符兜底
            rel = rel.replace(os.sep, "/")
            ext = os.path.splitext(path)[1] or "(no extension)"

            # 读取 UTF-8 内容
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                content = "[Error: Failed to decode file as UTF-8]"
            except Exception as e:
                content = f"[Error: {e}]"

            blocks.append("\n".join([
                "---",
                f"File: {rel}",
                f"Type: {ext}",
                "",
                content
            ]))

        final_text = "\n".join(blocks)
        if any((not blk.startswith("### 文件树")) for blk in blocks) and len(blocks) > 0:
            final_text += "\n---"

        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", final_text or "（未选择任何可导出的文本文件）")
        self._update_stats(final_text)

    def copy_to_clipboard(self):
        data = self.txt.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(data)
        try:
            self.update()  # 某些平台上需要这一步来“占有”剪贴板
        except Exception:
            pass
        messagebox.showinfo("已复制", f"内容已复制到剪贴板！\n\n{self.stats_var.get()}")

# ----------------------------- 启动 ----------------------------- #

def main():
    app = FileContextPackager()
    app.mainloop()

if __name__ == "__main__":
    # 改善 Windows 控制台编码显示（可选）
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    main()
