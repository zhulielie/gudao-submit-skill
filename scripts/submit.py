# -*- coding: utf-8 -*-
"""把作品交到鼓捣星球。只用标准库,不用装任何东西。

口令从环境变量 `GUDAO_SUBMIT_TOKEN` 读,**不接受命令行参数** ——
命令行会进 shell 历史、会出现在别人的 ps 里。
脚本自己也**永远不打印口令**,出错信息里也不带。

用法:
    GUDAO_SUBMIT_TOKEN=<口令> python submit.py <作品文件夹> \
        --title "作品名字" --scary no [--dry]
"""
import argparse
import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile

# Windows 的控制台默认是 GBK,打不出 ✔ ✗ 这些字符,脚本会当场崩(实测过)。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                          # noqa: BLE001
    pass

API = "https://gudao.games/api/submit"
ZIP_MAX = 24 * 1024 * 1024
HTML_MAX = 8 * 1024 * 1024
COVER_MAX = 2 * 1024 * 1024
PAD_CHOICES = ("contra", "wasd", "baozi", "dark", "")
FIT_CHOICES = ("fixed", "fill")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".vscode", ".idea"}


def pack(root):
    """把作品目录压成 zip。返回 (zip 字节, 文件数)。"""
    buf = io.BytesIO()
    n = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn == ".DS_Store":
                    continue
                full = os.path.join(dirpath, fn)
                z.write(full, os.path.relpath(full, root).replace("\\", "/"))
                n += 1
    return buf.getvalue(), n


def main():
    ap = argparse.ArgumentParser(description="把作品交到鼓捣星球")
    ap.add_argument("folder", help="作品文件夹(根目录要有 index.html)")
    ap.add_argument("--title", required=True, help="作品名字,最多 24 字")
    ap.add_argument("--scary", required=True, choices=("yes", "no"),
                    help="这个作品会不会突然吓人?**必答,别替作者猜**")
    ap.add_argument("--ai", default="", help="用了哪个 AI,最多 30 字")
    ap.add_argument("--notes", default="",
                    help="作品简介,最多 500 字。**过审后公开显示**")
    ap.add_argument("--mobile", action="store_true",
                    help="手机上真能玩才加;玩不了别加")
    ap.add_argument("--pad", default="", choices=PAD_CHOICES,
                    help="手机虚拟按钮键位;只用鼠标或触屏就留空")
    ap.add_argument("--fit", default=None, choices=FIT_CHOICES,
                    help="fixed=保持 16:9;fill=铺满屏幕")
    ap.add_argument("--cover", default=None, help="封面图片路径,可选,最多 2MB")
    ap.add_argument("--parent", default="",
                    help="要更新的作品编号;带了就是「某件的新版」")
    ap.add_argument("--dry", action="store_true",
                    help="只打印将要提交的东西,**不发请求**")
    a = ap.parse_args()

    root = os.path.abspath(a.folder)
    if not os.path.isdir(root):
        print("✗ 找不到这个文件夹:%s" % root)
        return 1
    if not os.path.isfile(os.path.join(root, "index.html")):
        inner = [d for d in os.listdir(root)
                 if os.path.isfile(os.path.join(root, d, "index.html"))]
        if not inner:
            print("✗ 根目录没有 index.html。入口文件必须叫 index.html,"
                  "放在包的最外面一层。")
            return 1

    if len(a.title) > 24:
        print("✗ 标题最多 24 个字,现在 %d 个" % len(a.title))
        return 1

    data, count = pack(root)
    if len(data) > ZIP_MAX:
        print("✗ 压缩包 %.1f MB,超过 24MB 上限" % (len(data) / 1048576))
        return 1

    body = {
        "title": a.title,
        "zip": base64.b64encode(data).decode("ascii"),
        "scary": a.scary,
        "pad": a.pad,
    }
    if a.ai:
        body["ai"] = a.ai[:30]
    if a.notes:
        body["notes"] = a.notes[:500]
    if a.mobile:
        body["mobile"] = True
    if a.fit is not None:
        body["fit"] = a.fit
    if a.parent:
        body["parent"] = a.parent
    if a.cover:
        if not os.path.isfile(a.cover):
            print("✗ 找不到封面文件:%s" % a.cover)
            return 1
        with open(a.cover, "rb") as f:
            cov = f.read()
        if len(cov) > COVER_MAX:
            print("✗ 封面 %.1f MB,超过 2MB 上限" % (len(cov) / 1048576))
            return 1
        body["cover"] = base64.b64encode(cov).decode("ascii")

    # 口令绝不进命令行、绝不打印。
    token = os.environ.get("GUDAO_SUBMIT_TOKEN", "").strip()

    print("要提交的东西")
    print("-" * 60)
    print("  文件夹    %s" % root)
    print("  文件数    %d 个,压缩包 %.2f MB" % (count, len(data) / 1048576))
    print("  标题      %s" % a.title)
    print("  会吓人吗  %s" % a.scary)
    print("  用了什么  %s" % (a.ai or "(没写)"))
    print("  简介      %s" % ((a.notes[:60] + "…") if len(a.notes) > 60
                              else (a.notes or "(没写)")))
    print("  手机可玩  %s   键位 %s   画面 %s"
          % ("是" if a.mobile else "否", a.pad or "(空)", a.fit or "(没声明)"))
    if a.parent:
        print("  这是新版  %s 的更新" % a.parent)
    print("  封面      %s" % ("有" if a.cover else "用默认卡带图"))
    print("  口令      %s" % ("已从 GUDAO_SUBMIT_TOKEN 读到" if token
                              else "**没读到**"))
    print("-" * 60)

    if a.dry:
        print("(--dry:只看看,没发请求)")
        return 0

    if not token:
        print()
        print("✗ 没读到投稿口令。让用户去拿一个:")
        print("    打开 https://gudao.games/submit.html ,登录后点「🎟️ 生成投稿口令」")
        print("    一小时内有效 · 只能用一次 · 只能用来投稿")
        print()
        print("  然后放进环境变量再跑一次(别写进命令行参数):")
        print("    GUDAO_SUBMIT_TOKEN=那一串 python submit.py ...")
        return 1

    req = urllib.request.Request(
        API, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json",
                 "X-Submit-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            out = json.loads(e.read().decode("utf-8"))
        except Exception:                                   # noqa: BLE001
            out = {}
        print()
        print("✗ 没交上去(HTTP %d):%s" % (e.code, out.get("error", "")))
        if out.get("need_phone"):
            print("  账号还没绑手机号。去 https://gudao.games/me.html 绑一下再来。")
        elif e.code == 403:
            print("  口令过期(1 小时)或者已经用过了 —— 让用户重新点一次生成。")
        return 1
    except urllib.error.URLError as e:
        print("✗ 连不上 gudao.games:%s" % e.reason)
        return 1

    if not out.get("ok"):
        print("✗ 没交上去:%s" % out.get("error", "(服务端没说原因)"))
        return 1

    sid = out.get("id") or out.get("sid") or "(服务端没回编号)"
    print()
    print("✔ 交上去了。投稿编号 %s" % sid)
    print()
    print("**还没公开** —— 要等站长人工过审才会出现在站上。")
    print("审核状态在 https://gudao.games/me.html 看。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
