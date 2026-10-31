# minicode/experiments/smoke_tools.py
# 运行：在 minicode/ 目录下  python -m experiments.smoke_tools
from minicode import config
from minicode.tools.registry import ToolError
from minicode.tools.read_file import ReadFileArgs, read_file
from minicode.tools.edit_file import EditFileArgs, edit_file
from minicode.tools.write_file import WriteFileArgs, write_file

config.set_workspace("scratch")

def expect_error(label, fn, args):
  try:
    fn(args)
    print(f"[FAIL] {label}：应当拒绝却成功了")
  except ToolError as e:
    print(f"[ok] {label}：{e}")

print(read_file(ReadFileArgs(path="app.py", limit=5)))
expect_error("路径逃逸", read_file, ReadFileArgs(path="../../week4_agent/main.py"))
expect_error("不唯一", edit_file, EditFileArgs(path="app.py", old_string="return None", new_string="return 0"))
expect_error("找不到", edit_file, EditFileArgs(path="app.py", old_string="不存在的字符串", new_string="x"))
print(edit_file(EditFileArgs(path="notes.txt", old_string="第二行", new_string="第二行（已改）")))
print("CRLF 保留：", b"\r\n" in (config.WORKSPACE / "notes.txt").read_bytes())
print(write_file(WriteFileArgs(path="new/dir/hello.py", content="print('hi')\n")))