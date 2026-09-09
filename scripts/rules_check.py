# -*- coding: utf-8 -*-
"""这份包里的规矩过期了没有?

为什么要它:鼓捣星球还在长,规矩和接口一直在改,而这个 skill 一旦被人装到本地,
就**停在打包那天**了。最糟的情况不是它不知道新规矩 —— 是它**照着旧规矩言之凿凿**。

做法很笨,但骗不了人:打包时把站上那两份规矩的指纹(sha256)记下来;
每次自检完,去站上再取一次,指纹不一样就说一句「站上改过了,去读一遍」。

- **只读两个公开的文本文件**(kit.txt / api.txt),不带任何身份、不发任何数据。
- **连不上就说连不上**,绝不当成「没改过」。
- **永远不改变自检的结论** —— 它只多说一句话,不会把绿的变红。

用法:
  python rules_check.py           # 看一眼:包里的规矩还新鲜吗
  python rules_check.py --盖章    # (维护者用)取当前站上的指纹,写进 rules_stamp.json
"""
import hashlib
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                            # noqa: BLE001
    pass

BASE = "https://gudao.games/"
DOCS = ("kit.txt", "api.txt")
STAMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules_stamp.json")
TIMEOUT = 6


def _fetch(name):
    """取一份;取不到就回 None —— 取不到是「不知道」,不是「没改」。"""
    import urllib.request
    try:
        req = urllib.request.Request(BASE + name,
                                     headers={"User-Agent": "gudao-skill/rules-check"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None
            return r.read()
    except Exception:                                        # noqa: BLE001
        return None


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def stamp():
    """维护者上架前跑一次:把站上现在这一版的指纹记下来。"""
    out = {"打包日": __import__("datetime").date.today().isoformat()}
    for name in DOCS:
        raw = _fetch(name)
        if raw is None:
            print("✗ 取不到 %s,没盖章(别在断网的时候盖章)" % name)
            return 1
        out[name] = {"sha256": _sha(raw), "bytes": len(raw)}
        print("  %-8s %d 字节  %s" % (name, len(raw), _sha(raw)[:16]))
    with io.open(STAMP, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("✔ 盖章:%s" % STAMP)
    return 0


def report(quiet_when_fresh=False):
    """回 (状态, 一句话)。状态:fresh / stale / unknown / nostamp。

    **调用方不许拿它当失败** —— 它只负责说话。
    """
    if not os.path.exists(STAMP):
        return ("nostamp", "这份包没记指纹,不知道规矩新不新 —— 交之前自己去读一遍 "
                           "https://gudao.games/kit.txt")
    try:
        with io.open(STAMP, encoding="utf-8") as f:
            s = json.load(f)
    except Exception:                                        # noqa: BLE001
        return ("nostamp", "指纹文件读不了,当作没有")

    changed, unknown = [], []
    for name in DOCS:
        want = (s.get(name) or {}).get("sha256")
        raw = _fetch(name)
        if raw is None:
            unknown.append(name)
        elif want and _sha(raw) != want:
            changed.append(name)

    day = s.get("打包日", "?")
    if changed:
        return ("stale",
                "⚠ **站上的规矩改过了**(%s 和这份包打包那天(%s)不一样)。\n"
                "   别照这份包里的说法回答具体问题,先读一遍:\n"
                "     curl -s https://gudao.games/kit.txt\n"
                "     curl -s https://gudao.games/api.txt"
                % ("、".join(changed), day))
    if unknown:
        return ("unknown",
                "· 没连上站上(%s),**不知道规矩有没有改**。这份包打包于 %s;"
                "能上网时先读一遍 kit.txt / api.txt,别当成最新的。"
                % ("、".join(unknown), day))
    if quiet_when_fresh:
        return ("fresh", "")
    return ("fresh", "· 规矩和这份包打包时(%s)一样,可以照着做。" % day)


def main():
    if "--盖章" in sys.argv or "--stamp" in sys.argv:
        return stamp()
    state, msg = report()
    if msg:
        print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
