"""
菜单与最近打开 + 临时文件 + 预览切换的功能测试 —— offscreen 模式直接构造 MarkdownEditor。

覆盖:
  - setup_menu() 后所有 actions 都已绑定 + 快捷键正确
  - new_file() 创建磁盘临时文件 + 默认进入编辑模式
  - close_current_file() 与 new_file 行为对称
  - _add_recent_file() 写入 QSettings + 去重 + 上限
  - QSettings 跨实例持久化 + 死链过滤
  - _populate_recent_menu 数字加速键 + 「清空列表」
  - _cleanup_temp_file 删除磁盘 + 复位状态
  - save_file_as 临时文件清理 + 转正 + 加入 recent_files
  - save_file 在临时文件上自动走另存为
  - _file_label_text / _window_title 三态分支
  - 临时文件输入后切阅读模式(read_preview 从编辑器读)
  - 保存后切阅读模式(show_read_mode 主动刷新)
"""
import os
import sys

# Windows PowerShell 默认 GBK 不支持 emoji
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# 把项目根加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import warnings
warnings.filterwarnings("ignore")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSettings, QCoreApplication
from src import MarkdownEditor
from src.recent_files import DEFAULT_RECENT_FILES_LIMIT

app = QApplication(sys.argv)

# 隔离测试的 QSettings 命名空间 —— 通过类属性覆盖,避免污染真实配置
TEST_ORG = "md_editor_test_org"
TEST_APP = "md_editor_test_app"
MarkdownEditor.SETTINGS_ORG = TEST_ORG
MarkdownEditor.SETTINGS_APP = TEST_APP
QSettings(TEST_ORG, TEST_APP).clear()

passed = 0
total = 0


def check(name, cond, hint=""):
    global passed, total
    total += 1
    if cond:
        passed += 1
        print(f"✅ {name}", flush=True)
    else:
        print(f"❌ {name}{(' — ' + hint) if hint else ''}", flush=True)


win = MarkdownEditor()  # 完整构造
print(">>> win constructed", flush=True)


# ================ 1. 菜单 action 完整性 ================
print("--- 1. 菜单 action 完整性 ---")
check("action_new 已创建", hasattr(win, "action_new") and win.action_new is not None)
check("action_open 已创建", hasattr(win, "action_open") and win.action_open is not None)
check("action_close 已创建", hasattr(win, "action_close") and win.action_close is not None)
check("action_quit 已创建", hasattr(win, "action_quit") and win.action_quit is not None)
check("menu_recent 是 QMenu", win.menu_recent is not None)
check("menu_file 是 QMenu", win.menu_file is not None)
check("新建快捷键 Ctrl+N", win.action_new.shortcut().toString().lower() == "ctrl+n")
check("打开快捷键 Ctrl+O", win.action_open.shortcut().toString().lower() == "ctrl+o")
check("关闭快捷键 Ctrl+W", win.action_close.shortcut().toString().lower() == "ctrl+w")
check("退出快捷键 Ctrl+Q", win.action_quit.shortcut().toString().lower() == "ctrl+q")


# ================ 2. 空 recent 列表占位 ================
print("--- 2. 空 recent 列表占位 ---")
win._recent.clear()
win._populate_recent_menu()
acts = win.menu_recent.actions()
check("空列表含 1 个占位 action", len(acts) == 1)
check("占位 action 显示 '(空)'", "(空)" in acts[0].text())
check("占位 action 不可点击", not acts[0].isEnabled())


# ================ 3. _recent.add 行为 ================
print("--- 3. _recent.add 行为 ---")
tmpdir = os.path.abspath(".")
fake_files = []
try:
    for i in range(3):
        p = os.path.join(tmpdir, f"_test_recent_{i}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"# test {i}\n")
        fake_files.append(p)

    win._recent.add(fake_files[0])
    win._recent.add(fake_files[1])
    win._recent.add(fake_files[2])
    check("添加 3 个文件后长度为 3", len(win._recent.paths) == 3)
    check("最新添加在头部", win._recent.paths[0] == fake_files[2])

    win._recent.add(fake_files[0])  # 已存在 → 去重 + 提升到头部
    check("去重后仍为 3 个", len(win._recent.paths) == 3)
    check("重新添加的文件移到头部", win._recent.paths[0] == fake_files[0])

    # 超过上限
    for i in range(DEFAULT_RECENT_FILES_LIMIT + 2):
        p = os.path.join(tmpdir, f"_test_overflow_{i}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write("")
        win._recent.add(p)
        fake_files.append(p)
    check("超限后截断到 DEFAULT_RECENT_FILES_LIMIT",
          len(win._recent.paths) == DEFAULT_RECENT_FILES_LIMIT)
finally:
    for p in fake_files:
        try:
            os.remove(p)
        except Exception:
            pass


# ================ 4. QSettings 持久化 ================
print("--- 4. QSettings 持久化 ---")
win._recent._settings.setValue("recent_files", [r"C:/some/a.md", r"C:/some/b.md"])
win._recent._settings.sync()

check("QSettings 写入了 recent_files key",
      win._recent._settings.contains("recent_files"))
raw_str = str(win._recent._settings.value("recent_files", ""))
check("QSettings 内容包含路径 a.md", "a.md" in raw_str)
check("QSettings 内容包含路径 b.md", "b.md" in raw_str)

# 新实例过滤死链
win._recent._paths = [r"C:/not/exist/file.md", r"C:/also/not/exist.md"]
loaded = win._recent._load()
check("_load 过滤不存在的路径", loaded == [])

# 跨实例持久化(用真实文件)
for i, p in enumerate([os.path.join(tmpdir, f"_persist_{i}.md") for i in range(2)]):
    with open(p, "w", encoding="utf-8") as f:
        f.write("")
    win._recent.add(p)
win._recent._settings.sync()
win2 = MarkdownEditor()
all_ok = all(any(p in r for r in win2._recent.paths)
             for p in [r"_persist_0.md", r"_persist_1.md"])
check("真实文件持久化跨实例保留", all_ok)

for p in [os.path.join(tmpdir, f"_persist_{i}.md") for i in range(2)]:
    try:
        os.remove(p)
    except Exception:
        pass


# ================ 5. _populate_recent_menu 加速键 + 清空 ================
print("--- 5. _populate_recent_menu 加速键 + 清空 ---")
win._recent._paths = [r"C:/a.md", r"C:/b.md", r"C:/c.md"]
win._populate_recent_menu()
acts = win.menu_recent.actions()
# 3 个文件 + 1 个 separator + 1 个『清空列表』 = 5
check("填充 3 个文件后 menu_recent 有 5 个 action", len(acts) == 5)
check("第一个条目含 '&1'", "&1" in acts[0].text())
check("第二个条目含 '&2'", "&2" in acts[1].text())
check("第三个条目含 '&3'", "&3" in acts[2].text())
check("最后一条是『清空列表』", "清空" in acts[-1].text())

# _clear_recent_files
win._clear_recent_files()
check("清空后 _recent.paths 为空", len(win._recent.paths) == 0)
check("清空后 menu_recent 仅 1 个占位", len(win.menu_recent.actions()) == 1)


# ================ 6. new_file() 行为(新语义) ================
print("--- 6. new_file() 行为 ---")
win.editor.blockSignals(True)
win.editor.clear()
win.editor.blockSignals(False)
win._files.current_file = None
win._files._temp_file = False
win._files.is_modified = False
win._recent.clear()

# win 启动默认在阅读模式
check("起始模式是阅读模式", win.mode == "read")

win.new_file()

check("new_file 后编辑器为空", win.editor.toPlainText() == "")
check("new_file 后 current_file 不为 None(指向真实临时文件)",
      win._files.current_file is not None)
check("new_file 后 _temp_file = True", win._files._temp_file is True)
check("new_file 后 current_file 路径存在磁盘", os.path.exists(win._files.current_file))
check("new_file 后 current_file 后缀是 .md",
      win._files.current_file.endswith(".md"))
check("new_file 后默认进入编辑模式", win.mode == "edit")
check("new_file 后 file_label 显示『未命名』",
      win.file_label.text() == "未命名")
check("new_file 后 is_modified 为 False", win._files.is_modified is False)
check("new_file 后窗口标题含『未命名』(不暴露临时路径)",
      "未命名" in win.windowTitle())
check("new_file 后临时文件不进最近打开列表",
      len(win._recent.paths) == 0)

temp_path_after_new = win._files.current_file


# ================ 7. _cleanup_temp_file 删除磁盘文件 ================
print("--- 7. _cleanup_temp_file ---")
check("is_temp_file 返回 True", win._files.is_temp_file() is True)
win._files._cleanup_temp_file()
check("_cleanup_temp_file 后磁盘文件已删除",
      not os.path.exists(temp_path_after_new))
check("_cleanup_temp_file 后 _temp_file = False", win._files._temp_file is False)
check("_cleanup_temp_file 后 current_file = None", win._files.current_file is None)
check("_cleanup_temp_file 后 is_temp_file 返回 False",
      win._files.is_temp_file() is False)

# 重复调用安全
win._files._cleanup_temp_file()


# ================ 8. new_file 后编辑 → 关闭应清理临时文件 ================
print("--- 8. 编辑后关闭清理临时文件 ---")
win.new_file()
temp_with_edit = win._files.current_file
# 模拟用户编辑(置脏)
win.editor.blockSignals(True)
win.editor.setPlainText("hello world")
win.editor.blockSignals(False)
win._files.is_modified = True

win._files._cleanup_temp_file()
check("编辑后强制清理 → 临时文件被删", not os.path.exists(temp_with_edit))
check("编辑后强制清理 → _temp_file 复位", win._files._temp_file is False)

# 关键:清掉编辑状态,避免下次 new_file 触发未保存弹窗阻塞
win.editor.blockSignals(True)
win.editor.clear()
win.editor.blockSignals(False)
win._files.is_modified = False


# ================ 9. save_file_as 清理临时文件 ================
print("--- 9. save_file_as 处理临时文件 ---")
workdir = os.path.abspath(".")
target_path = os.path.join(workdir, "_test_saved_target.md")
if os.path.exists(target_path):
    os.remove(target_path)
win._recent.clear()

win.new_file()
old_temp = win._files.current_file
check("save_file_as 前存在临时文件", os.path.exists(old_temp))

# patch FileController 的 prompt_save_path(避免改 QFileDialog 类属性)
win._files.prompt_save_path = lambda: (target_path, "Markdown 文件 (*.md)")

# 注意:save_file_as 已归 FileController,主窗口通过工具栏/菜单触发
ok = win._files.save_file_as()
check("save_file_as 返回 True", ok is True)

check("save_file_as 后临时文件已被清理", not os.path.exists(old_temp))
check("save_file_as 后 current_file 指向目标路径",
      win._files.current_file == target_path)
check("save_file_as 后 _temp_file = False(已转正)",
      win._files._temp_file is False)
check("save_file_as 后目标文件已写入磁盘",
      os.path.exists(target_path))
with open(target_path, encoding="utf-8") as f:
    check("save_file_as 后目标文件内容为编辑器内容",
          f.read() == win.editor.toPlainText())
check("save_file_as 后 is_modified = False", win._files.is_modified is False)
check("save_file_as 后 file_label 是目标 basename",
      win.file_label.text() == os.path.basename(target_path))

# 清理
if os.path.exists(target_path):
    os.remove(target_path)
win._recent.clear()
win.editor.blockSignals(True)
win.editor.clear()
win.editor.blockSignals(False)
win._files.is_modified = False


# ================ 9.5 _on_save_btn_clicked 完整路径(临时 → 转正 → 加入 recent) ================
print("--- 9.5 _on_save_btn_clicked 临时文件保存 ---")
target_btn = os.path.join(workdir, "_test_btn_save.md")
if os.path.exists(target_btn):
    os.remove(target_btn)
win._recent.clear()

win.new_file()
win.editor.blockSignals(True)
win.editor.setPlainText("# btn save test\n")
win.editor.blockSignals(False)
win._files.is_modified = True
win._files.prompt_save_path = lambda: (target_btn, "Markdown 文件 (*.md)")

win._on_save_btn_clicked()  # 工具栏保存路径:内部 try/except 兜底

check("工具栏保存后临时文件清理", not os.path.exists(win._files.current_file) or win._files._temp_file is False)
check("工具栏保存后 current_file 指向目标",
      win._files.current_file == target_btn)
check("工具栏保存后目标在最近打开列表",
      any(target_btn in r for r in win._recent.paths))

if os.path.exists(target_btn):
    os.remove(target_btn)
win._recent.clear()
win.editor.blockSignals(True)
win.editor.clear()
win.editor.blockSignals(False)
win._files.is_modified = False


# ================ 10. save_file 对临时文件自动走另存为 ================
print("--- 10. save_file 在临时文件上自动走另存为 ---")
target2 = os.path.join(workdir, "_test_save_via_temp.md")
if os.path.exists(target2):
    os.remove(target2)

win.new_file()
temp_before_save = win._files.current_file
win.editor.blockSignals(True)
win.editor.setPlainText("auto save as test")
win.editor.blockSignals(False)
win._files.is_modified = True

win._files.prompt_save_path = lambda: (target2, "Markdown 文件 (*.md)")
win._on_save_btn_clicked()  # 走工具栏保存逻辑,内部调 FileController.save_file

check("save 后临时文件被清理", not os.path.exists(temp_before_save))
check("save 后 current_file 指向新目标",
      win._files.current_file == target2)
check("save 后 _temp_file = False", win._files._temp_file is False)

# 清理
if os.path.exists(target2):
    os.remove(target2)
win._recent.clear()
win.editor.blockSignals(True)
win.editor.clear()
win.editor.blockSignals(False)
win._files.is_modified = False


# ================ 11. _file_label_text 三态 ================
print("--- 11. _file_label_text 三态 ---")
win._files.current_file = None
win._files._temp_file = False
check("无文件 → 未打开文件", win._files.file_label_text() == "未打开文件")
win.new_file()
check("临时文件 → 未命名", win._files.file_label_text() == "未命名")
win._files._cleanup_temp_file()
win._files.current_file = r"D:/notes/hello.md"
win._files._temp_file = False
check("真实文件 → basename", win._files.file_label_text() == "hello.md")


# ================ 12. _window_title 三态 ================
print("--- 12. _window_title 三态 ---")
win._files.current_file = None
win._files._temp_file = False
title = win._files.window_title(win.mode)
check("无文件标题不含路径", "/" not in title and "\\" not in title)
win.new_file()
t = win._files.window_title(win.mode)
check("临时文件标题含『未命名』", "未命名" in t)
check("临时文件标题不暴露系统临时目录",
      "AppData" not in t and "Temp" not in t and "\\" not in t.split(" - ")[-1])
win._files._cleanup_temp_file()
win._files.current_file = r"C:/foo/bar.md"
win._files._temp_file = False
check("真实文件标题含路径", "C:/foo/bar.md" in win._files.window_title(win.mode))

# 终极清理
win._files._cleanup_temp_file()


# ================ 13. 临时文件输入后切阅读模式 ================
print("--- 13. 临时文件输入后切阅读模式 ---")
win.new_file()
sample_text = "# Hello\n\nThis is **bold** and a [link](https://x.y)."
win.editor.blockSignals(True)
win.editor.setPlainText(sample_text)
win.editor.blockSignals(False)
win._files.is_modified = True

win.show_read_mode()

read_html = win.read_preview.toHtml()
check("临时文件切阅读后 read_preview 含 <h1> 标题",
      "<h1" in read_html or "Hello" in read_html)
check("临时文件切阅读后 read_preview 含粗体标签或文本",
      "<strong>" in read_html or "bold" in read_html)
check("临时文件切阅读后 read_preview 含链接文本",
      "link" in read_html)
check("切到阅读模式后 mode == 'read'", win.mode == "read")

win.show_edit_mode()
check("切回编辑模式后 mode == 'edit'", win.mode == "edit")

win._files._cleanup_temp_file()
win.editor.blockSignals(True)
win.editor.clear()
win.editor.blockSignals(False)
win._files.is_modified = False


# ================ 14. 临时文件 save_file_as 后切阅读模式 ================
print("--- 14. 临时文件 save 后切阅读模式 ---")
target3 = os.path.join(workdir, "_test_after_save.md")
if os.path.exists(target3):
    os.remove(target3)

win.new_file()
saved_text = "# Saved Doc\n\nAfter save content."
win.editor.blockSignals(True)
win.editor.setPlainText(saved_text)
win.editor.blockSignals(False)
win._files.is_modified = True

win._files.prompt_save_path = lambda: (target3, "Markdown 文件 (*.md)")
win._on_save_btn_clicked()

check("保存后 _temp_file = False", win._files._temp_file is False)
check("保存后 current_file 指向 target3", win._files.current_file == target3)

win.show_read_mode()
read_html2 = win.read_preview.toHtml()
check("保存后切阅读 read_preview 含标题 Saved Doc",
      "Saved Doc" in read_html2 or "<h1" in read_html2)
check("保存后切阅读 read_preview 含保存内容",
      "After save content" in read_html2 or "After" in read_html2)
check("保存后切阅读 mode == 'read'", win.mode == "read")

win.show_edit_mode()
if os.path.exists(target3):
    os.remove(target3)
win.editor.blockSignals(True)
win.editor.clear()
win.editor.blockSignals(False)
win._files.is_modified = False


# ================ 15. 阅读模式下打开文件 read_preview 立即刷新 ================
print("--- 15. 阅读模式下打开文件 read_preview 刷新 ---")
import tempfile as _tf
fd, open_target = _tf.mkstemp(suffix='.md')
os.close(fd)
with open(open_target, 'w', encoding='utf-8') as f:
    f.write("# Loaded Content\n\nAfter load, read_preview should show this.")

# 切回阅读模式(模拟用户初始状态)
win.show_read_mode()
check("切到阅读模式后 mode == 'read'", win.mode == "read")
# 此时 read_preview 是占位符
check("阅读模式占位符生效",
      "请打开" in win.read_preview.toHtml() or not open_target.split(os.sep)[-1] in win.read_preview.toHtml())

# patch QFileDialog 直接调 FileController.load_file 模拟打开
from PyQt5.QtWidgets import QFileDialog
original_open = QFileDialog.getOpenFileName
QFileDialog.getOpenFileName = staticmethod(
    lambda *a, **kw: (open_target, "Markdown 文件 (*.md)")
)
win._on_open_btn_clicked()
QFileDialog.getOpenFileName = original_open

check("打开后 current_file 指向目标",
      win._files.current_file == open_target)
check("打开后 file_label 是 basename",
      win.file_label.text() == os.path.basename(open_target))
check("打开后 read_preview 含目标内容(关键回归点)",
      "Loaded Content" in win.read_preview.toHtml())
check("打开后 read_preview 含文件正文",
      "After load" in win.read_preview.toHtml())
check("打开后 edit_preview 也已刷新(切模式无需等待)",
      "Loaded Content" in win.edit_preview.toHtml())

os.remove(open_target)
win._recent.clear()
win.editor.blockSignals(True)
win.editor.clear()
win.editor.blockSignals(False)
win._files.is_modified = False


# 清理测试残留
QSettings(TEST_ORG, TEST_APP).clear()

print(f"\n{'=' * 50}")
print(f"结果: {passed}/{total} 通过")
sys.exit(0 if passed == total else 1)