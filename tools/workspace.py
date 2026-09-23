#!/usr/bin/env python3
"""研究网页的生成与检查入口。

    python tools/workspace.py build     由具名段落重建 index/dashboard/attempts
    python tools/workspace.py check     归档哈希、来源指纹、相对链接、状态合法性

设计约束（改动前先读）：

* **一个来源，多种视图。** 页面内容只从四份现役文件里**具名段落**读取：
  CONTROL_PANEL.md / paper/PROPOSAL.md / related_work/AI_READY_EVIDENCE_MATRIX.md /
  archive/README.md。不另建 dashboard JSON 状态副本。
* **生成页自包含。** 内容、样式与锚点全部内嵌，`file:///…/dashboard.html` 直接打开即可，
  不需要 fetch 本地 Markdown，也不需要后端，因此没有 React/Vue/数据库。
* **缺东西就失败。** 缺具名段落、状态值不在允许集合、链接目标不存在时抛错，
  不静默生成空白页，也不沿用上一次的状态。
* **时间与指纹取自真实来源。** 页面上的更新时间来自总控的元数据块；指纹是四份来源
  字节的 SHA-256 前缀，所以「今天重新生成」不会伪装成研究有更新。指纹不含生成页本身，
  避免循环。
* **链接策略。** 指向 Pages 白名单内文件的链接保持仓库相对路径（本地 file:// 与站点都能用）；
  其余仓库文件改为固定基线上的 GitHub 入口，这样白名单外的证据仍可按既有方式进入。
  基线用 --link-base 指定，默认 main。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path

GENERATOR_VERSION = "workspace.py v1"
REPO_SLUG = "TIaomiao/Event-Provenance-Harness"

PANEL = "CONTROL_PANEL.md"
PROPOSAL = "paper/PROPOSAL.md"
MATRIX = "related_work/AI_READY_EVIDENCE_MATRIX.md"
ARCHIVE_INDEX = "archive/README.md"

# 生成页只发布这些路径；其余仓库文件走 GitHub 入口
PAGES_ALLOWLIST = {
    "dashboard.html",
    "attempts.html",
    "CONTROL_PANEL.md",
    "paper/PROPOSAL.md",
    "related_work/AI_READY_EVIDENCE_MATRIX.md",
}

PANEL_SECTIONS = [
    "当前快照",
    "当前任务",
    "最新可核验交付",
    "已定选择与来源",
    "阻塞与下一步",
    "下一次给师兄",
]
PROPOSAL_SECTIONS = [
    "论文概览",
    "Benchmark v0.1 工作稿",
    "问题",
    "目标使用者与使用场景",
    "输入与输出",
    "整体架构",
    "组件与现有实现对照",
    "候选任务",
    "方法与对照",
    "指标、答案依据与成本",
    "主张映射表与主结果表",
    "公平性",
    "候选消融",
    "已有素材的定位",
    "当前局限",
    "待上级判断",
]
MATRIX_SECTIONS = ["精选阅读", "阅读卡", "证据状态定义", "检索边界与待核缺口"]
ARCHIVE_SECTIONS = ["主题索引"]

ALLOWED_STAGES = {"用户首轮阅读与研究反馈", "文献与任务/对照设计", "系统与验证", "成稿与投稿"}
REQUIRED_META = ["updated", "stage", "verified_commit"]

# 论文概览里必须能被机器取到的字段：首屏要用它们做标题与副标题
OVERVIEW_FIELDS = ["工作题目", "一句话"]

OUTPUTS = ["index.html", "dashboard.html", "attempts.html"]

# 活动文件里允许出现的相对链接根（其余按缺失处理）
NUMBERING = re.compile(r"^(?:[一二三四五六七八九十]+、|\d+[.、)]\s*)+")


class Fail(Exception):
    """明确失败：不产出半成品页面。"""


# --------------------------------------------------------------------------- markdown

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm_heading(text: str) -> str:
    return NUMBERING.sub("", text.strip()).strip()


def parse_headings(text: str) -> list[tuple[int, str, int]]:
    """返回 (level, normalized_title, line_index)。跳过围栏代码块。"""
    out = []
    fence = False
    for i, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = re.match(r"^(#{2,4})\s+(.*?)\s*$", line)
        if m:
            out.append((len(m.group(1)), norm_heading(m.group(2)), i))
    return out


def extract_section(text: str, key: str, source: str) -> str:
    lines = text.splitlines()
    heads = parse_headings(text)
    matches = [(lv, t, i) for lv, t, i in heads if t == key or t.startswith(key)]
    if not matches:
        raise Fail(f"{source}: 缺少具名段落「{key}」")
    if len(matches) > 1:
        raise Fail(f"{source}: 具名段落「{key}」不唯一（{len(matches)} 处匹配）")
    level, _, start = matches[0]
    end = len(lines)
    for lv, _, i in heads:
        if i > start and lv <= level:
            end = i
            break
    return "\n".join(lines[start + 1 : end]).strip("\n")


def meta_block(text: str, source: str) -> dict[str, str]:
    m = re.search(r"<!--\s*workspace-meta\s*(.*?)-->", text, re.S)
    if not m:
        raise Fail(f"{source}: 缺少 <!-- workspace-meta --> 元数据块")
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    for k in REQUIRED_META:
        if not meta.get(k):
            raise Fail(f"{source}: 元数据块缺少 `{k}`")
    if meta["stage"] not in ALLOWED_STAGES:
        raise Fail(
            f"{source}: stage=`{meta['stage']}` 不在允许集合 {sorted(ALLOWED_STAGES)}"
        )
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["updated"]):
        raise Fail(f"{source}: updated 必须是 YYYY-MM-DD，当前 `{meta['updated']}`")
    return meta


_SPLIT_ROW = re.compile(r"(?<!\\)\|")


def _cells(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip().replace("\\|", "|") for c in _SPLIT_ROW.split(row)]


def _inline(text: str, resolve) -> str:
    out = html.escape(text, quote=False)

    def link(m: re.Match[str]) -> str:
        label, url = m.group(1), m.group(2)
        href = resolve(url)
        return f'<a href="{html.escape(href, quote=True)}">{label}</a>'

    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def render_markdown(text: str, resolve) -> str:
    """渲染本项目实际用到的 Markdown 子集：标题、段落、列表、表格、引用、围栏代码。"""
    lines = text.splitlines()
    html_parts: list[str] = []
    i, n = 0, len(lines)
    para: list[str] = []
    list_open: str | None = None

    def flush_para() -> None:
        if para:
            html_parts.append("<p>" + _inline(" ".join(para), resolve) + "</p>")
            para.clear()

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            html_parts.append(f"</{list_open}>")
            list_open = None

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_para(); close_list()
            lang = stripped[3:].strip()
            buf: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="lang-{html.escape(lang)}"' if lang else ""
            html_parts.append(
                f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>"
            )
            continue

        if not stripped:
            flush_para(); close_list(); i += 1; continue

        m = re.match(r"^(#{2,4})\s+(.*)$", stripped)
        if m:
            flush_para(); close_list()
            lv = len(m.group(1))
            title = _inline(m.group(2), resolve)
            anchor = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", m.group(2)).strip("-")
            html_parts.append(f'<h{lv} id="{anchor}">{title}</h{lv}>')
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < n and re.match(
            r"^\|[\s:\-|]+\|$", lines[i + 1].strip()
        ):
            flush_para(); close_list()
            header = _cells(lines[i])
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append(_cells(lines[i]))
                i += 1
            th = "".join(f"<th>{_inline(c, resolve)}</th>" for c in header)
            trs = []
            for row in body:
                row = (row + [""] * len(header))[: len(header)]
                trs.append(
                    "<tr>" + "".join(f"<td>{_inline(c, resolve)}</td>" for c in row) + "</tr>"
                )
            html_parts.append(
                f'<div class="tw"><table><thead><tr>{th}</tr></thead>'
                f"<tbody>{''.join(trs)}</tbody></table></div>"
            )
            continue

        if stripped.startswith("> "):
            flush_para(); close_list()
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            html_parts.append(
                "<blockquote>" + _inline(" ".join(buf), resolve) + "</blockquote>"
            )
            continue

        m = re.match(r"^(?:- |\* )", stripped)
        if m:
            flush_para()
            if list_open != "ul":
                close_list(); html_parts.append("<ul>"); list_open = "ul"
            html_parts.append(f"<li>{_inline(stripped[2:], resolve)}</li>")
            i += 1
            continue

        m = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if m:
            flush_para()
            if list_open != "ol":
                close_list(); html_parts.append("<ol>"); list_open = "ol"
            html_parts.append(f"<li>{_inline(m.group(1), resolve)}</li>")
            i += 1
            continue

        if stripped in {"---", "***", "___"}:
            flush_para(); close_list(); html_parts.append("<hr>"); i += 1; continue

        para.append(stripped)
        i += 1

    flush_para(); close_list()
    return "\n".join(html_parts)


# --------------------------------------------------------------------------- links

def make_resolver(repo: Path, source_rel: str, link_base: str):
    src_dir = (repo / source_rel).parent

    def resolve(url: str) -> str:
        url = url.strip()
        if re.match(r"^(?:https?:|mailto:|#|data:)", url):
            return url
        path, _, anchor = url.partition("#")
        if not path:
            return url
        target = (src_dir / path).resolve()
        try:
            rel = target.relative_to(repo).as_posix()
        except ValueError:
            raise Fail(f"{source_rel}: 链接 `{url}` 指向仓库外")
        if not target.exists():
            raise Fail(f"{source_rel}: 链接 `{url}` 的目标不存在（{rel}）")
        suffix = f"#{anchor}" if anchor else ""
        if rel in PAGES_ALLOWLIST or target.is_dir():
            return rel + suffix
        return f"https://github.com/{REPO_SLUG}/blob/{link_base}/{rel}{suffix}"

    return resolve


# --------------------------------------------------------------------------- page shell

CSS = """
:root{--ink:#16241f;--muted:#5f6f69;--line:#dfe6e2;--bg:#f6f8f7;--card:#fff;
--accent:#0d6b57;--accent-soft:#e6f2ee;--warn:#8a5a00;--warn-soft:#fdf3e0}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.68 "Microsoft YaHei","PingFang SC","Segoe UI",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:28px 22px 64px}
header.top{border-bottom:3px solid var(--accent);padding-bottom:18px;margin-bottom:22px}
.eyebrow{font:600 12px/1 "Segoe UI",sans-serif;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
h1.title{font-size:31px;line-height:1.24;margin:10px 0 8px}
h1.title em{font-style:normal;color:var(--accent)}
.sub{color:var(--muted);font-size:15px;margin:0}
.stamp{margin-top:14px;display:flex;flex-wrap:wrap;gap:8px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:999px;
padding:5px 12px;font:13px/1.5 "Segoe UI",sans-serif;color:var(--muted)}
.chip b{color:var(--ink)}
.chip.stage{background:var(--accent-soft);border-color:#bfdfd5;color:var(--accent);font-weight:700}
nav.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}
nav.tabs a{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:8px 14px;text-decoration:none;color:var(--ink);font-weight:600;font-size:14px}
nav.tabs a:hover{border-color:var(--accent);color:var(--accent)}
section.block{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:20px 22px;margin-bottom:20px}
section.block>h2{margin:0 0 4px;font-size:21px}
section.block>.hint{color:var(--muted);font-size:13px;margin:0 0 16px}
h3{font-size:17px;margin:22px 0 8px}
h4{font-size:15px;margin:18px 0 6px;color:var(--muted)}
p{margin:9px 0}
ul,ol{margin:9px 0;padding-left:22px}
li{margin:5px 0}
code{background:#eef2f0;border-radius:4px;padding:1px 5px;
font:13.5px/1.5 "Cascadia Mono",Consolas,monospace}
pre{background:#f2f5f3;border:1px solid var(--line);border-radius:8px;
padding:14px;overflow-x:auto}
pre code{background:none;padding:0;font-size:13px;line-height:1.6}
blockquote{margin:12px 0;padding:10px 16px;background:var(--accent-soft);
border-left:4px solid var(--accent);border-radius:0 8px 8px 0;color:#20493f}
.tw{overflow-x:auto;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:#f0f4f2;font-weight:700;white-space:nowrap}
tbody tr:nth-child(even){background:#fafcfb}
a{color:var(--accent)}
footer{color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:16px}
.note{background:var(--warn-soft);border-left:4px solid var(--warn);border-radius:0 8px 8px 0;
padding:10px 14px;margin:12px 0;font-size:14.5px;color:#5c3d00}
@media print{
 body{background:#fff}
 nav.tabs{display:none}
 section.block{border:none;padding:0;margin-bottom:16px;break-inside:avoid}
 .tw,table,pre{break-inside:avoid}
 a{color:var(--ink);text-decoration:none}
}
"""


def page(title: str, body: str, subtitle: str, header_note: str = "") -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<!-- 生成文件，勿手改：由 tools/workspace.py build 从现役 Markdown 的具名段落生成 -->
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header class="top">
<div class="eyebrow">EHR Harness / Research</div>
<h1 class="title">{subtitle}</h1>
<div class="stamp">{header_note}</div>
</header>
{body}
<footer>
<p>本页由 <code>tools/workspace.py build</code> 生成，源是 CONTROL_PANEL.md、paper/PROPOSAL.md、
related_work/AI_READY_EVIDENCE_MATRIX.md 与 archive/README.md 的具名段落。
患者正文、受控参考答案、凭据与原始模型响应不在本页，也不在本仓库。</p>
</footer>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------- build

def load_sources(repo: Path) -> dict[str, str]:
    src = {}
    for rel in (PANEL, PROPOSAL, MATRIX, ARCHIVE_INDEX):
        path = repo / rel
        if not path.is_file():
            raise Fail(f"来源文件不存在：{rel}")
        src[rel] = path.read_text(encoding="utf-8")
    return src


def build(repo: Path, link_base: str) -> dict[str, object]:
    src = load_sources(repo)
    meta = meta_block(src[PANEL], PANEL)

    sections: dict[str, str] = {}
    for key in PANEL_SECTIONS:
        sections[f"panel:{key}"] = extract_section(src[PANEL], key, PANEL)
    for key in PROPOSAL_SECTIONS:
        sections[f"proposal:{key}"] = extract_section(src[PROPOSAL], key, PROPOSAL)
    for key in MATRIX_SECTIONS:
        sections[f"matrix:{key}"] = extract_section(src[MATRIX], key, MATRIX)
    for key in ARCHIVE_SECTIONS:
        sections[f"archive:{key}"] = extract_section(src[ARCHIVE_INDEX], key, ARCHIVE_INDEX)

    # 首屏的题目与一句话直接取自「论文概览」，不在这里另写一份
    overview = sections["proposal:论文概览"]
    fields: dict[str, str] = {}
    for name in OVERVIEW_FIELDS:
        match = re.search(rf"\*\*{re.escape(name)}\*\*\s*[：:]\s*(.+)", overview)
        if not match:
            raise Fail(f"{PROPOSAL}: 「论文概览」缺少字段「**{name}**：…」")
        fields[name] = match.group(1).strip().rstrip("。")

    fingerprints = {rel: sha256_bytes(text.encode("utf-8")) for rel, text in src.items()}
    combined = hashlib.sha256(
        "".join(sorted(fingerprints.values())).encode("ascii")
    ).hexdigest()[:12]

    resolvers = {rel: make_resolver(repo, rel, link_base) for rel in src}

    def render(key: str) -> str:
        rel = key.split(":", 1)[0]
        owner = {
            "panel": PANEL,
            "proposal": PROPOSAL,
            "matrix": MATRIX,
            "archive": ARCHIVE_INDEX,
        }[rel]
        return render_markdown(sections[key], resolvers[owner])

    stage = meta["stage"]
    stamp = (
        f'<span class="chip stage">当前阶段：{html.escape(stage)}</span>'
        f'<span class="chip">来源更新时间 <b>{html.escape(meta["updated"])}</b></span>'
        f'<span class="chip">来源内容指纹 <b>{combined}</b></span>'
        f'<span class="chip">构建版本 <b>{GENERATOR_VERSION}</b></span>'
        f'<span class="chip">核验基线 <b>{html.escape(meta["verified_commit"])}</b></span>'
    )

    tabs = """<nav class="tabs">
<a href="#paper">论文概览</a>
<a href="#overview">当前概览</a>
<a href="#reading">阅读与反馈</a>
<a href="#system">系统与验证</a>
<a href="#evidence">当前证据</a>
<a href="#advisor">下一次给师兄</a>
<a href="attempts.html">历史资料</a>
</nav>"""

    dash = f"""{tabs}
<section class="block" id="paper">
<h2>论文题目与研究概览</h2>
<p class="hint">题目与下面这段概览取自 paper/PROPOSAL.md 的「论文概览」：它是当前假设与方案的工作稿，不是已验证结论。</p>
{render("proposal:论文概览")}
</section>

<section class="block" id="overview">
<h2>当前概览</h2>
<p class="hint">方向、阶段、当前任务与最近一项有证据的交付。数字与状态都取自总控面板。</p>
{render("panel:当前快照")}
<h3>当前任务</h3>
{render("panel:当前任务")}
<h3>最新可核验交付</h3>
{render("panel:最新可核验交付")}
<h3>已定选择与来源</h3>
{render("panel:已定选择与来源")}
</section>

<section class="block" id="reading">
<h2>阅读与反馈</h2>
<p class="hint">别人怎么定义 AI-ready、怎么设对照、怎么证明收益。DSH 核验进度与用户阅读进度分开记；
摘要级条目不得引用数字。完整台账见 related_work/AI_READY_EVIDENCE_MATRIX.md。</p>
{render("matrix:阅读卡")}
<h3>精选阅读</h3>
{render("matrix:精选阅读")}
<h3>证据状态定义</h3>
{render("matrix:证据状态定义")}
<h3>检索边界与待核缺口</h3>
{render("matrix:检索边界与待核缺口")}
</section>

<section class="block" id="system">
<h2>系统与验证</h2>
<p class="hint">下面是目标结构，不等于已实现。组件状态分成「代码存在 / 离线测试通过 / 有历史运行 / 端到端验证」四件事。</p>
<h3>问题</h3>
{render("proposal:问题")}
<h3>目标使用者与使用场景</h3>
{render("proposal:目标使用者与使用场景")}
<h3>输入与输出</h3>
{render("proposal:输入与输出")}
<h3>整体架构</h3>
{render("proposal:整体架构")}
<h3>Benchmark v0.1 工作稿</h3>
{render("proposal:Benchmark v0.1 工作稿")}
<h3>组件与现有实现对照</h3>
{render("proposal:组件与现有实现对照")}
<h3>候选任务</h3>
{render("proposal:候选任务")}
<h3>方法与对照</h3>
{render("proposal:方法与对照")}
<h3>公平性</h3>
{render("proposal:公平性")}
<h3>候选消融：多层级处理</h3>
{render("proposal:候选消融")}
</section>

<section class="block" id="evidence">
<h2>当前证据</h2>
<p class="hint">新方案尚未运行，成绩一律 NOT_RUN。已有实验是历史探索结果，不占主结果位置。</p>
<h3>指标、答案依据与成本</h3>
{render("proposal:指标、答案依据与成本")}
<h3>已有素材的定位</h3>
{render("proposal:已有素材的定位")}
<h3>当前局限</h3>
{render("proposal:当前局限")}
<h3>阻塞与下一步</h3>
{render("panel:阻塞与下一步")}
</section>

<section class="block" id="advisor">
<h2>下一次给师兄</h2>
<p class="hint">可以是阅读与设计进展，不强迫有新实验数字。</p>
{render("panel:下一次给师兄")}
<h3>待上级判断</h3>
{render("proposal:待上级判断")}
</section>

<section class="block" id="history">
<h2>历史资料</h2>
<p class="hint">历史只经索引追溯，不在本页展开。旧规划、旧结果与旧命令不产生待办。</p>
<ul>
<li><a href="attempts.html">历史目录视图（attempts.html）</a>：按主题分的历史探索、会议决策、文献纠错与整理快照。</li>
<li><a href="https://github.com/{REPO_SLUG}/blob/{link_base}/archive/README.md">唯一历史索引（archive/README.md）</a></li>
<li><a href="https://github.com/{REPO_SLUG}/blob/{link_base}/results/">证据库 results/</a>：允许回传的匿名聚合结果与运行记录。</li>
</ul>
</section>
"""

    dashboard = page(
        f'{fields["工作题目"]} · 研究总览',
        dash,
        f'{html.escape(fields["工作题目"])}<br><em>{html.escape(fields["一句话"])}</em>',
        stamp,
    )

    attempts_body = f"""<nav class="tabs"><a href="dashboard.html">← 回到当前总览</a></nav>
<section class="block">
<h2>历史资料</h2>
<p class="hint">本页只作历史目录视图，不承担当前研究叙事。归档材料只作证据，不产生执行指令。</p>
{render("archive:主题索引")}
</section>
<section class="block">
<h2>归档批次</h2>
<p class="hint">整理前原件与逐份哈希。</p>
<ul>
<li><code>archive/20260919_workspace_c14e4b2/</code>：2026-09-19 工作区收敛快照（清单见同目录 manifest.json）。</li>
<li><code>archive/document_cleanup_20260908_1727/</code>、<code>archive/legacy_20260915/</code>、<code>archive/context-v001/</code>、<code>archive/planning/</code>、<code>archive/migration/</code>、<code>archive/results_snapshot_20260915/</code>。</li>
</ul>
</section>
"""
    attempts = page(
        "历史资料 · EHR Harness",
        attempts_body,
        "历史资料<em>按主题索引追溯</em>",
        f'<span class="chip">来源更新时间 <b>{html.escape(meta["updated"])}</b></span>'
        f'<span class="chip">来源内容指纹 <b>{combined}</b></span>'
        f'<span class="chip">构建版本 <b>{GENERATOR_VERSION}</b></span>',
    )

    index = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=dashboard.html">
<title>EHR Harness 研究总览</title>
<!-- 生成文件，勿手改：由 tools/workspace.py build 生成 -->
</head>
<body style="font-family:'Microsoft YaHei',sans-serif;padding:24px;color:#16241f">
<p>正在打开研究总览……若没有自动跳转，请点
<a href="dashboard.html" style="color:#0d6b57;font-weight:700">dashboard.html</a>。</p>
<p style="color:#5f6f69;font-size:14px">历史资料：<a href="attempts.html" style="color:#0d6b57">attempts.html</a></p>
</body>
</html>
"""

    written = {}
    for name, content in (
        ("index.html", index),
        ("dashboard.html", dashboard),
        ("attempts.html", attempts),
    ):
        path = repo / name
        path.write_text(content, encoding="utf-8")
        written[name] = len(content.encode("utf-8"))

    return {
        "meta": meta,
        "fingerprint": combined,
        "fingerprints": fingerprints,
        "written": written,
        "sections": sorted(sections),
        "fields": fields,
    }


# --------------------------------------------------------------------------- check

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FORBIDDEN = re.compile(
    r"sk-[A-Za-z0-9]{20,}|/home/[A-Za-z0-9_]+/code/[A-Za-z0-9_/]+"
    r"|[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}"
)

ACTIVE_DOCS = [
    "README.md",
    "AGENTS.md",
    PANEL,
    PROPOSAL,
    MATRIX,
    ARCHIVE_INDEX,
    "src/prototype/README.md",
    "src/evaluation/README.md",
    "src/evaluation/DESIGN.md",
    "results/README.md",
]


def check(repo: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []

    # 1. 来源与具名段落
    try:
        built = build(repo, link_base="main")
    except Fail as exc:
        return [f"生成失败：{exc}"], notes
    notes.append(
        f"具名段落 OK：{len(built['sections'])} 段；指纹 {built['fingerprint']}"
    )
    notes.append(
        "生成页字节：" + "、".join(f"{k}={v}" for k, v in sorted(built["written"].items()))
    )

    # 2. 相对链接
    broken = 0
    for rel in ACTIVE_DOCS:
        path = repo / rel
        if not path.is_file():
            errors.append(f"活动文件缺失：{rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for m in LINK_RE.finditer(text):
            url = m.group(1)
            if re.match(r"^(?:https?:|mailto:|#|data:)", url):
                continue
            target = (path.parent / url.split("#")[0]).resolve()
            if not target.exists():
                errors.append(f"断链：{rel} → {url}")
                broken += 1
    notes.append(f"活动文件相对链接检查：{len(ACTIVE_DOCS)} 份文件，断链 {broken} 条")

    # 3. 归档 manifest
    manifests = sorted((repo / "archive").glob("*/manifest.json"))
    for mf in manifests:
        data = json.loads(mf.read_text(encoding="utf-8"))
        rel_dir = mf.parent.relative_to(repo).as_posix()
        bad = 0
        registered = {e["archive_path"] for e in data.get("entries", [])}
        for entry in data.get("entries", []):
            target = repo / entry["archive_path"]
            if not target.is_file():
                errors.append(f"{rel_dir}: 归档文件缺失 {entry['archive_path']}")
                bad += 1
                continue
            if sha256_bytes(target.read_bytes()) != entry["sha256"]:
                errors.append(f"{rel_dir}: 哈希不符 {entry['archive_path']}")
                bad += 1
            # 归档必须真的入 git：被 .gitignore 命中的文件在克隆后不存在，
            # manifest 会指向缺失路径（PDF 规则就曾漏掉两份归档原件）
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", entry["archive_path"]],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            if tracked.returncode != 0:
                errors.append(f"{rel_dir}: 归档文件未纳入 git：{entry['archive_path']}")
                bad += 1
            for e in data.get("entries", []):
                if e["action"] == "move" and (repo / e["original_path"]).exists():
                    errors.append(f"{rel_dir}: 应已移出但仍存在 {e['original_path']}")
                    bad += 1
                    break
        on_disk = {
            p.relative_to(repo).as_posix()
            for p in mf.parent.rglob("*")
            if p.is_file() and p.name != "manifest.json"
        }
        for extra in sorted(on_disk - registered):
            errors.append(f"{rel_dir}: 批次内文件未登记进 manifest：{extra}")
            bad += 1
        notes.append(f"{rel_dir}: {len(data.get('entries', []))} 条登记，异常 {bad}")

    # 4. 生成页
    for name in OUTPUTS:
        path = repo / name
        if not path.is_file():
            errors.append(f"生成页缺失：{name}")
            continue
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN.search(text):
            errors.append(f"{name}: 命中被拦截的内容模式（凭据/服务器绝对路径/完整时间戳）")
        if "<script" in text.lower():
            errors.append(f"{name}: 生成页不应包含脚本")
        if "fetch(" in text:
            errors.append(f"{name}: 生成页不得 fetch 本地 Markdown")

    dash = (repo / "dashboard.html").read_text(encoding="utf-8")
    for need in ("来源内容指纹", built["fingerprint"], built["meta"]["stage"]):
        if need not in dash:
            errors.append(f"dashboard.html 未包含 {need!r}")
    if "workspace.py build" not in dash:
        errors.append("dashboard.html 缺少「生成文件」说明")
    for name, value in built["fields"].items():
        if value not in dash:
            errors.append(f"dashboard.html 首屏未显示论文概览字段 {name}={value!r}")
    paper_at, overview_at = dash.find('id="paper"'), dash.find('id="overview"')
    if paper_at < 0:
        errors.append("dashboard.html 缺少论文概览区块（id=\"paper\"）")
    elif overview_at >= 0 and paper_at > overview_at:
        errors.append("dashboard.html 首屏顺序错：论文概览必须在当前概览之前")

    # 4b. 单文件可用性：页内锚点必须存在，且不得引用外部资源
    for name in OUTPUTS:
        path = repo / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        ids = set(re.findall(r'\sid="([^"]+)"', text))
        for anchor in set(re.findall(r'href="#([^"]+)"', text)):
            if anchor not in ids:
                errors.append(f"{name}: 页内锚点 #{anchor} 没有对应的 id")
        if re.search(r'<(?:img|script|link|iframe)\b[^>]*(?:src|href)="https?://', text):
            errors.append(f"{name}: 引用了外部资源，file:// 下不可靠")

    # 5. Pages 白名单与站点视图：以工作流为准，不另设一份清单
    wf_path = repo / ".github/workflows/pages.yml"
    if not wf_path.is_file():
        errors.append("缺少 .github/workflows/pages.yml")
    else:
        wf = wf_path.read_text(encoding="utf-8")
        checked_block = re.search(r"for f in \\\n(.*?)\n\s*do\b", wf, re.S)
        cpairs = re.findall(r"^\s*cp\s+(\S+)\s+(_site\S*)\s*$", wf, re.M)
        exists_set = (
            set(re.findall(r"^\s+(\S+?)\s*\\?$", checked_block.group(1), re.M))
            if checked_block
            else set()
        )
        cp_set = {src for src, _ in cpairs}
        if not exists_set:
            errors.append("pages.yml: 未解析到存在性检查清单")
        if exists_set != cp_set:
            errors.append(
                "pages.yml: 存在性检查与 cp 清单不一致 "
                f"(只在检查 {sorted(exists_set - cp_set)}；只在 cp {sorted(cp_set - exists_set)})"
            )
        for src in sorted(cp_set):
            if not (repo / src).is_file():
                errors.append(f"pages.yml 白名单指向不存在的文件：{src}")
        site_paths = set()
        for src, dest in cpairs:
            site_paths.add(
                f"{dest}{Path(src).name}" if dest.endswith("/") else dest
            )
        site_paths = {p[len("_site/"):] if p.startswith("_site/") else p for p in site_paths}
        notes.append(f"Pages 白名单：{len(cp_set)} 个源文件，站点 {len(site_paths)} 个路径")
        for src in sorted(cp_set):
            if src.endswith(".html"):
                text = (repo / src).read_text(encoding="utf-8")
                for href in set(re.findall(r'href="([^"]+)"', text)):
                    if re.match(r"^(?:https?:|#|mailto:)", href):
                        continue
                    target = (repo / src).parent / href.split("#")[0]
                    rel = target.resolve().relative_to(repo).as_posix()
                    if rel not in site_paths:
                        errors.append(
                            f"{src}: 相对链接 {href} 在站点上不存在（{rel}）"
                        )

    # 6. 页面不得整段嵌入归档原件（取每份归档长文的最长行做抽查）
    archived = [
        p
        for p in (repo / "archive").rglob("*")
        if p.is_file() and p.suffix in {".md", ".html"} and p.stat().st_size > 4000
    ]
    leaks = 0
    for p in archived:
        try:
            lines = sorted(
                (l.strip() for l in p.read_text(encoding="utf-8", errors="ignore").splitlines()),
                key=len,
                reverse=True,
            )
        except OSError:
            continue
        for line in lines[:2]:
            if len(line) >= 80 and line in dash:
                errors.append(f"dashboard.html 疑似整段嵌入归档原件：{p.name}")
                leaks += 1
                break
    notes.append(f"归档全文嵌入抽查：{len(archived)} 份长文，命中 {leaks}")

    return errors, notes


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="研究网页生成与检查")
    ap.add_argument("command", choices=["build", "check"])
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument(
        "--link-base",
        default="main",
        help="白名单外仓库链接指向的 git 基线（默认 main）",
    )
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    if args.command == "build":
        try:
            result = build(repo, args.link_base)
        except Fail as exc:
            print(f"BUILD FAILED: {exc}", file=sys.stderr)
            return 1
        print(f"stage       : {result['meta']['stage']}")
        print(f"updated     : {result['meta']['updated']}")
        print(f"fingerprint : {result['fingerprint']}")
        for name, value in result["fields"].items():
            print(f"  {name}: {value}")
        for name, size in result["written"].items():
            print(f"  wrote {name} ({size} bytes)")
        return 0

    errors, notes = check(repo)
    for n in notes:
        print(f"note: {n}")
    if errors:
        print("\nCHECK FAILED:")
        for e in errors:
            print("  -", e)
        return 1
    print("\nCHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
