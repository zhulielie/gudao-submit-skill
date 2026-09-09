# -*- coding: utf-8 -*-
"""鼓捣星球投稿自检 —— 离线跑,不联网,不改任何文件。

为什么要它:作品跑在 `default-src 'none'; connect-src 'none'` 底下,
**外部资源一个都取不到,而你本地测的时候一切正常**。
等传上去被退回,已经浪费了一轮。这个脚本把能机器查的那部分先查掉。

**扫描本身完全离线**,不联网、不改任何文件。只有跑完之后会去站上取一次
`kit.txt` / `api.txt` 的指纹,看这份包里的规矩过期没有(不带身份、不发数据,
连不上就说连不上)。加 `--不联网` 连这一步也不做。

退出码:
  0  干净,可以交
  1  **肯定过不了**(外部网址 / 网络 API / 缺 index.html / 超限)—— 先改代码
  2  没有硬错,但有几处**要人看一眼**(可能在收集个人信息)

用法:  python preflight.py <作品文件夹> [--不联网]
"""
import os
import re
import sys

# ── 平台限制(出自 https://gudao.games/api.txt) ──────────────────────
ZIP_MAX = 24 * 1024 * 1024          # 压缩包
UNZIP_MAX = 96 * 1024 * 1024        # 解开后
FILE_MAX = 24 * 1024 * 1024         # 包里任何单个文件
HTML_ONLY_MAX = 8 * 1024 * 1024     # 走 "html" 字段交单文件时的上限
COUNT_MAX = 800                     # 文件数
DEPTH_MAX = 12                      # 目录层数

# Windows 的控制台默认是 GBK,打不出 ✔ ✗ 这些字符,脚本会当场崩(实测过)。
# 创作者里很大一部分在 Windows —— 这一段不能省。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                          # noqa: BLE001
    pass

TEXT_EXT = {".html", ".htm", ".js", ".mjs", ".cjs", ".css", ".json",
            ".svg", ".xml", ".txt", ".md", ".ts"}

# ── 外部网址:只挑「会去取东西」的位置 ─────────────────────────────
#  故意不用一条大正则 —— 每条都要能单独关掉、单独解释。
FETCHING_ATTR = re.compile(
    r"""(?:src|href|srcset|poster|data-src|action|content)\s*=\s*["']\s*(https?:)?//""",
    re.I)
CSS_URL = re.compile(r"""(?:@import\s+|url\(\s*)["']?\s*(https?:)?//""", re.I)
IMPORT_FROM = re.compile(
    r"""(?:^|[^\w])(?:import|export)\b[^;\n]*?["']\s*(https?:)?//""", re.M)
META_REFRESH = re.compile(r"""http-equiv\s*=\s*["']?refresh""", re.I)

# 网络 API:CSP 的 connect-src 是 'none',这些一个都发不出去
NET_API = re.compile(
    r"""\b(fetch\s*\(|XMLHttpRequest|new\s+WebSocket|new\s+EventSource"""
    r"""|navigator\.sendBeacon|\.ajax\s*\(|axios\s*[.(])""")

# 不算数的:XML 命名空间不是请求
NAMESPACE_OK = re.compile(
    r"""(?:xmlns|xmlns:\w+|xml:base)\s*=\s*["']\s*https?://""", re.I)

# ── 个人信息:只报「要人看一眼」,不当硬错 ──────────────────────────
#  「你叫什么名字」给角色起名是正常的,「请输入真实姓名」不是。
#  机器分不清这两个,所以这里只挑出来给人看。
PII_WORDS = ("真实姓名", "真名", "学校", "班级", "手机号", "电话号",
             "家庭住址", "身份证", "QQ号", "微信号", "联系方式")
PII_NEARBY = re.compile(r"""<input|<textarea|placeholder|prompt\s*\(|请输入|请填写""")


def walk(root):
    """列出包里所有文件。跳过 .git 和常见的构建缓存。"""
    skip = {".git", "node_modules", "__pycache__", ".vscode", ".idea"}
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if fn == ".DS_Store":
                continue
            out.append(os.path.join(dirpath, fn))
    return out


def read_text(path):
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError:
            return None
    return None


def scan_text(path, rel, errors, warns):
    txt = read_text(path)
    if txt is None:
        return
    lines = txt.split("\n")
    for i, line in enumerate(lines, 1):
        # 命名空间那种先摘掉,免得误报
        probe = NAMESPACE_OK.sub("", line)
        hit = None
        if FETCHING_ATTR.search(probe):
            hit = "外部网址(src/href/srcset/poster 这类)"
        elif CSS_URL.search(probe):
            hit = "外部网址(CSS 的 @import / url())"
        elif IMPORT_FROM.search(probe):
            hit = "外部网址(import 语句)"
        elif META_REFRESH.search(probe) and re.search(r"https?://", probe, re.I):
            hit = "外部网址(meta refresh 跳转)"
        if hit:
            errors.append((rel, i, hit, line.strip()[:110]))
            continue
        m = NET_API.search(probe)
        if m:
            # 就算这段是「兜底/永远跑不到」的死路径,留着也没用 ——
            # connect-src 'none' 让它必然失败。删掉比留着强。
            errors.append((rel, i, "网络 API(%s)—— connect-src 是 'none',必然失败,删掉"
                           % m.group(1).strip("( ."), line.strip()[:110]))
            continue
        if PII_NEARBY.search(line):
            for w in PII_WORDS:
                if w in line:
                    warns.append((rel, i, "可能在问「%s」" % w, line.strip()[:110]))
                    break


def rules_note(offline):
    """跑完说一句:这份包里的规矩过期没有。

    ⚠ 它**不许影响退出码**。自检的结论只由作品本身决定;
      规矩新不新是另一件事,说出来给人听,不替人做判断。
    """
    if offline:
        print()
        print("· 没查站上的规矩(你加了 --不联网)。交之前自己读一遍 "
              "https://gudao.games/kit.txt")
        return
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import rules_check
        state, msg = rules_check.report()
        if msg:
            print()
            print(msg)
    except Exception:                                      # noqa: BLE001
        print()
        print("· 没能查站上的规矩,**不知道有没有改**。别当成最新的。")


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    offline = ("--不联网" in sys.argv) or ("--offline" in sys.argv)
    if not argv:
        print("用法: python preflight.py <作品文件夹> [--不联网]")
        return 1
    root = os.path.abspath(argv[0])
    if not os.path.isdir(root):
        print("✗ 找不到这个文件夹:%s" % root)
        return 1

    print("自检:%s" % root)
    print("=" * 70)
    errors, warns, notes = [], [], []

    files = walk(root)
    if not files:
        print("✗ 文件夹是空的")
        return 1

    # ① index.html 必须在最外面一层
    #    外面多套一层文件夹是允许的(服务端会剥掉),所以两层都认。
    tops = {os.path.relpath(p, root).replace("\\", "/") for p in files}
    has_root_index = "index.html" in tops
    wrapped = [p for p in tops if p.count("/") == 1 and p.endswith("/index.html")]
    if not has_root_index and not wrapped:
        errors.append(("(整个包)", 0, "根目录没有 index.html",
                       "入口文件必须叫 index.html,放在包的最外面一层"))
    elif not has_root_index:
        notes.append("index.html 在 %s —— 外面多套了一层,服务端会自己剥掉,可以" % wrapped[0])

    # ② 体积、文件数、目录层数
    total = 0
    for p in files:
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        total += sz
        rel = os.path.relpath(p, root).replace("\\", "/")
        if sz > FILE_MAX:
            errors.append((rel, 0, "单个文件超过 24MB", "%.1f MB" % (sz / 1048576)))
        depth = rel.count("/") + 1
        if depth > DEPTH_MAX:
            errors.append((rel, 0, "目录超过 12 层", "第 %d 层" % depth))
    if len(files) > COUNT_MAX:
        errors.append(("(整个包)", 0, "文件数超过 800",
                       "现在 %d 个" % len(files)))
    if total > UNZIP_MAX:
        errors.append(("(整个包)", 0, "解开后超过 96MB",
                       "现在 %.1f MB" % (total / 1048576)))

    # ③ 逐个文本文件扫红线
    for p in files:
        if os.path.splitext(p)[1].lower() not in TEXT_EXT:
            continue
        try:
            if os.path.getsize(p) > 8 * 1024 * 1024:
                notes.append("%s 太大(>8MB),跳过没扫"
                             % os.path.relpath(p, root).replace("\\", "/"))
                continue
        except OSError:
            continue
        scan_text(p, os.path.relpath(p, root).replace("\\", "/"), errors, warns)

    # ── 报结果 ─────────────────────────────────────────────────
    print("文件 %d 个,合计 %.2f MB" % (len(files), total / 1048576))
    if len(files) == 1 and has_root_index:
        sz = os.path.getsize(os.path.join(root, "index.html"))
        if sz > HTML_ONLY_MAX:
            print("提醒:单文件走 html 字段上限 8MB,这份 %.1f MB —— 压成 zip 交"
                  % (sz / 1048576))
    for n in notes:
        print("  · %s" % n)
    print()

    if errors:
        print("✗ 过不了的 %d 处 —— 这些改完再交:" % len(errors))
        for rel, ln, why, ctx in errors[:60]:
            where = "%s:%d" % (rel, ln) if ln else rel
            print("   %-40s %s" % (where, why))
            print("   %s│ %s" % (" " * 40, ctx))
        if len(errors) > 60:
            print("   ...还有 %d 处" % (len(errors) - 60))
        print()

    if warns:
        print("⚠ 要你自己看一眼的 %d 处(机器分不清,所以不替你判):" % len(warns))
        print("  红线是「不许问真实姓名、学校、班级、手机号」。")
        print("  给游戏角色起名字是正常的;让玩家填真实身份不行。")
        for rel, ln, why, ctx in warns[:30]:
            print("   %-40s %s" % ("%s:%d" % (rel, ln), why))
            print("   %s│ %s" % (" " * 40, ctx))
        if len(warns) > 30:
            print("   ...还有 %d 处" % (len(warns) - 30))
        print()

    if errors:
        print("=" * 70)
        print("结论:**先改,别交。** 传上去也是退回。")
        rules_note(offline)
        return 1
    if warns:
        print("=" * 70)
        print("结论:没有硬错。上面那几处**确认一下不是在收集真实身份**就能交。")
        rules_note(offline)
        return 2
    print("=" * 70)
    print("结论:✔ 干净,可以交。")
    print()
    print("注意:这个脚本只查得了机器能查的部分。**内容红线(血腥/色情/赌博/抄袭/")
    print("政治敏感/自绘中国地图)机器查不了,那部分靠你和用户自己把关。**")
    rules_note(offline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
