# 鼓捣星球投稿 Skill

> 一句话:**让 AI 帮你把做好的网页游戏发到 [鼓捣星球](https://gudao.games)。**

鼓捣星球是个作品站 —— AI 做的网页游戏和小工具,传上去过审后点开就能玩。
逛的人里很多是小学生。**一个 60 行的换算器和两万行的游戏,在这个站上是平等的作品。**

装上这个 skill 之后,你只要跟 AI 说人话:

```
帮我做一个小猫接星星的游戏,做完发到鼓捣星球
```

AI 会自动知道:平台的作品跑在 `default-src 'none'` 底下连不了外网、入口必须叫
`index.html`、哪些内容是红线、怎么打包、怎么交。**你不用再交代一遍平台的事。**

---

## 装

**Claude Code / Codex CLI / 任何读 `SKILL.md` 的 agent:**

```bash
git clone https://github.com/zhulielie/gudao-submit-skill ~/.claude/skills/gudao-submit
```

Windows:

```powershell
git clone https://github.com/zhulielie/gudao-submit-skill "$env:USERPROFILE\.claude\skills\gudao-submit"
```

装好后跟 AI 说「帮我发到鼓捣星球」就会自动用上。

只要 Python 3.8+,**不用装任何第三方包**(只用标准库)。

---

## 它替你做什么

### 1 · 做之前就知道约束

作品跑在这个 CSP 底下:

```
default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:;
connect-src 'none'; frame-src 'none'; object-src 'none'
```

意思是 **`fetch` / `WebSocket` / 外部 CDN 一个都用不了**。
本地测一切正常,传上去白屏 —— 站上的 NO HUMAN THERE 就这么坏了很久,
因为从 esm.sh 引 Babylon。**改动只有一行,但没人提前说。**

这个 skill 存在的主要理由就是让 AI 提前知道这些,而不是做完了再返工。

### 2 · 交之前自检

```bash
python scripts/preflight.py <作品文件夹>
```

离线扫一遍,不联网、不改文件:

| 查什么 | 判成什么 |
|---|---|
| `src`/`href`/`@import`/`url()`/importmap 里的外部网址 | 过不了 |
| `fetch` / `XMLHttpRequest` / `WebSocket` / `EventSource` / `sendBeacon` | 过不了 |
| 根目录有没有 `index.html` | 过不了 |
| 体积 / 文件数 / 目录层数超限 | 过不了 |
| 像是在问真实姓名、学校、班级、手机号 | **要人看一眼**(机器分不清起名字和收集身份) |

不误报:`xmlns="http://www.w3.org/2000/svg"`、`data:` / `blob:` URI、
站内的 `/g/_lib/…`、相对路径引用 —— 全都放过。

> 实测:拿站上真实投稿件跑,6/6 全绿,零误报。

### 3 · 交

```bash
GUDAO_SUBMIT_TOKEN=<一次性口令> python scripts/submit.py <作品文件夹> \
    --title "小猫接星星" --scary no --ai "Claude" --notes "方向键移动"
```

先加 `--dry` 演练一次,只打印将要提交的东西,**不发请求**。

---

## 关于那个口令(这是这套东西的关键设计)

**AI 不需要、也拿不到你的账号。**

你在 <https://gudao.games/submit.html> 登录后点一下「🎟️ 生成投稿口令」,
把那一串给 AI 就行:

```
一小时内有效 · 只能用一次 · 只能用来投稿
```

泄了最坏是一小时内被代投一件,**而且还得过人工审核**。它读不了私信、
改不了头像、删不掉任何东西。

脚本从环境变量 `GUDAO_SUBMIT_TOKEN` 读它,**不接受命令行参数**
(命令行会进 shell 历史、会出现在别人的 `ps` 里),自己也永远不打印它。

---

## 三条红线

踩了直接下架,不走流程。**就三条**,每条都有理由:

1. **不连外部网站** —— CSP 拦得死死的,而且外链会把访客的 IP 漏给第三方。
2. **内容红线** —— 血腥写实、色情低俗、辱骂歧视、赌博与诱导消费、广告导流、
   抄袭搬运、违法与政治敏感。
   *打斗本身没问题,骰子纸牌本身没问题;问题是往写实残忍走、押上东西赌输赢。*
   **恐怖不禁,不打招呼地吓人才禁** —— 投稿时如实填 `--scary yes` 不影响过审。
3. **不许问真实姓名、学校、班级、手机号** —— **这条是法律要求的,没有例外。**

完整版规矩:<https://gudao.games/kit.txt>(约 42KB)
接口字段表:<https://gudao.games/api.txt>

**这两份是唯一权威,而且会更新。** 本 skill 只摘了最要命的部分,
拿不准就去读那两份。

---

## English

**Publish AI-made browser games to [Gudao Planet](https://gudao.games)** (鼓捣星球),
a Chinese creator platform where AI-generated web games and tools get played.

Install into `~/.claude/skills/`, then just say *"make a game and publish it to
Gudao Planet."* The skill teaches your agent the platform's hard constraints
**before** it writes code:

- Works run under `default-src 'none'; connect-src 'none'` — **no CDN, no `fetch`,
  no WebSocket**. Bundle everything locally or inline it.
- Entry point must be `index.html` at the package root.
- Three hard rules: no external network, content restrictions (the site has minors),
  no collecting real names / schools / phone numbers.

Includes an offline pre-flight linter (`scripts/preflight.py`, stdlib only) and a
submitter (`scripts/submit.py`) that uses a **single-use, one-hour, submit-only
token** — your agent never touches your account credentials.

Works with Claude Code, Codex CLI, Cursor, Gemini CLI, and anything else that
reads `SKILL.md`.

---

## 许可

MIT。规矩本身出自鼓捣星球站上的《投稿规则》和开工包,以站上那两份为准。
