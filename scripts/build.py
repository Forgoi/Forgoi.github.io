#!/usr/bin/env python3
"""Build Forgoi's static blog using only the Python 3.10+ standard library.

The intentionally small Markdown subset is documented in README.md.
No network, timestamps, external templates, or build-time dependencies.
"""
from __future__ import annotations

import html
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'blog-src'
SITE = json.loads((SOURCE / 'site.json').read_text(encoding='utf-8'))
BASE = SITE['url'].rstrip('/')
CSS_REV = hashlib.sha256((SOURCE / 'static' / 'style.css').read_bytes()).hexdigest()[:12]
JS_REV = hashlib.sha256((SOURCE / 'static' / 'site.js').read_bytes()).hexdigest()[:12]
GENERATED: list[str] = []


def esc(value):
    return html.escape(str(value), quote=True)


def safe_url(value):
    value = value.strip()
    return value if re.match(r'^(https?://|/|#|mailto:)', value) else '#'


def inline(text):
    """Escape all raw HTML, then render inline code, links and emphasis."""
    tokens = []
    def reserve(fragment):
        tokens.append(fragment)
        return f'\x00{len(tokens)-1}\x00'
    text = re.sub(r'`([^`]+)`', lambda m: reserve('<code>' + esc(m[1]) + '</code>'), text)
    text = re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', lambda m: reserve(f'<a href="{esc(safe_url(m[2]))}">{inline(m[1])}</a>'), text)
    text = esc(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
    return re.sub(r'\x00(\d+)\x00', lambda m: tokens[int(m[1])], text)


def highlighted(code, language):
    if language.lower() not in ('c#', 'cs', 'csharp', 'python', 'py'):
        return esc(code)
    keyword = r'\b(?:using|namespace|class|public|private|protected|static|void|int|float|double|bool|string|var|if|else|while|for|foreach|return|new|true|false|null|def|import|from|print|in|None|True|False)\b'
    pattern = re.compile(r'(?P<comment>//[^\n]*|\#[^\n]*)|(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(?P<keyword>' + keyword + r')|(?P<number>\b\d+(?:\.\d+)?[fFdD]?\b)')
    chunks, last = [], 0
    for match in pattern.finditer(code):
        chunks.append(esc(code[last:match.start()]))
        chunks.append(f'<span class="syntax-{match.lastgroup}">{esc(match[0])}</span>')
        last = match.end()
    chunks.append(esc(code[last:]))
    return ''.join(chunks)


def markdown(text):
    if text.startswith('---\n'):
        text = text.split('\n---', 1)[1].lstrip('\n')
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    lines = text.splitlines()
    output, headings = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('```'):
            language = line[3:].strip() or 'text'
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(lines[i]); i += 1
            if i == len(lines):
                raise ValueError('Unclosed fenced code block')
            output.append(f'<div class="code-block"><div class="code-toolbar"><span>{esc(language.upper())}</span><button class="copy-code" type="button" aria-label="复制代码" aria-live="polite">复制</button></div><pre tabindex="0"><code>{highlighted(chr(10).join(code), language)}</code></pre></div>')
            i += 1
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading:
            level, label = len(heading[1]), heading[2]
            anchor = f'section-{len(headings)+1}'
            headings.append((level, label, anchor))
            output.append(f'<h{level} id="{anchor}">{inline(label)}</h{level}>')
            i += 1
            continue
        if re.match(r'^\s*[-*_]{3,}\s*$', line):
            output.append('<hr>'); i += 1; continue
        if line.startswith('>'):
            quote_lines = []
            while i < len(lines) and lines[i].startswith('>'):
                quote_lines.append(re.sub(r'^>\s?', '', lines[i])); i += 1
            output.append('<blockquote>' + markdown('\n'.join(quote_lines))[0] + '</blockquote>')
            continue
        if i + 1 < len(lines) and '|' in line and re.match(r'^\s*\|?\s*:?-{3,}:?\s*\|', lines[i+1]):
            cells = lambda s: [p.strip() for p in s.strip().strip('|').split('|')]
            table = '<div class="table-scroll" tabindex="0" role="region" aria-label="数据表，可横向滚动"><table><thead><tr>'
            table += ''.join(f'<th scope="col">{inline(c)}</th>' for c in cells(line)) + '</tr></thead><tbody>'
            i += 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                table += '<tr>' + ''.join('<td>' + inline(c) + '</td>' for c in cells(lines[i])) + '</tr>'
                i += 1
            output.append(table + '</tbody></table></div>')
            continue
        listing = re.match(r'^(?:([-*])|(\d+)\.)\s+(.+)$', line)
        if listing:
            ordered = bool(listing[2]); tag = 'ol' if ordered else 'ul'
            start = f' start="{listing[2]}"' if ordered and listing[2] != '1' else ''
            items = []
            while i < len(lines):
                match = re.match(r'^(?:([-*])|(\d+)\.)\s+(.+)$', lines[i])
                if not match or bool(match[2]) != ordered:
                    break
                items.append('<li>' + inline(match[3]) + '</li>'); i += 1
            output.append(f'<{tag}{start}>' + ''.join(items) + f'</{tag}>')
            continue
        paragraph = [line]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#{1,6}\s|```|>|[-*]\s|\d+\.\s)', lines[i]):
            if i + 1 < len(lines) and re.match(r'^\s*\|?\s*:?-{3,}:?\s*\|', lines[i+1]):
                break
            paragraph.append(lines[i]); i += 1
        output.append('<p>' + inline('\n'.join(paragraph)) + '</p>')
    return '\n'.join(output), headings


def write(path, content):
    dest = ROOT / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        dest.write_bytes(content)
    else:
        dest.write_text(content, encoding='utf-8')
    GENERATED.append(path)


def header(active):
    nav = [('首页', '/', 'home'), ('文章', '/archives/', 'archives'), ('学习路线', '/learning/', 'learning')]
    links = ''.join(f'<a href="{path}"' + (' aria-current="page"' if key == active else '') + f'>{label}</a>' for label, path, key in nav)
    return f'''<a class="skip" href="#main">跳转到正文</a><div class="wrap"><header class="site-header"><a class="brand" href="/" aria-label="Forgoi 首页"><span class="brand-mark" aria-hidden="true">f.</span><span class="brand-name">Forgoi</span><span class="brand-caption">学习手记</span></a><nav class="nav" aria-label="主导航">{links}<a class="github" href="{SITE['repository']}" aria-label="在 GitHub 查看博客源码">GitHub <span aria-hidden="true"><svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></span></a></nav></header></div>'''


def footer():
    return '''<div class="wrap"><footer class="site-footer"><span class="footer-brand">FORGOI <span aria-hidden="true">/</span> 学习，记录，继续。</span><div class="footer-links"><a href="/about/">关于本站</a><a href="/atom.xml">RSS 订阅</a><a href="https://github.com/Forgoi/Forgoi.github.io">源码 <svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></a></div></footer></div>'''


def page(title, body, path='/', active='', description=None, article=None):
    full_title = f'{title} · Forgoi' if title else 'Forgoi · Unity 学习手记'
    description = description or SITE['description']
    schema = {'@context':'https://schema.org', '@type':'BlogPosting' if article else 'WebSite','name':title or SITE['name'],'url':BASE+path, 'inLanguage':'zh-CN'}
    if article:
        schema.update({'headline':title,'datePublished':article['date'],'author':{'@type':'Person','name':'Forgoi'},'description':description})
    schema_json = json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c')
    home_assets = ''
    if active == 'home':
        home_rev = hashlib.sha256((SOURCE / 'static' / 'starfield.css').read_bytes() + (SOURCE / 'static' / 'starfield.js').read_bytes()).hexdigest()[:12]
        home_assets = f'<link rel="stylesheet" href="/assets/starfield.css?v={home_rev}"><script src="/assets/starfield.js?v={home_rev}" defer></script>'
    counter_script = '<script async src="https://busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js"></script>' if article else ''
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(full_title)}</title><meta name="description" content="{esc(description)}">
<meta name="theme-color" content="{'#060a12' if active == 'home' else '#f8faff'}"><meta name="color-scheme" content="{'dark' if active == 'home' else 'light'}">
<link rel="canonical" href="{esc(BASE+path)}"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/atom+xml" title="Forgoi · Unity 学习手记" href="/atom.xml">
<meta property="og:type" content="{'article' if article else 'website'}"><meta property="og:title" content="{esc(full_title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(BASE+path)}"><meta property="og:locale" content="zh_CN">
<link rel="stylesheet" href="/assets/style.css?v={CSS_REV}"><script src="/assets/site.js?v={JS_REV}" defer></script>
<script type="application/ld+json">{schema_json}</script>{home_assets}
</head><body{' class="cosmic-home"' if active == 'home' else ''}>{header(active)}<main class="wrap" id="main">{body}</main>{footer()}{counter_script}</body></html>
'''


ROUTES = [
    ('01', '数据布局与缓存', '完成缓存行、AoS / SoA 与组件数组的概念阅读。', '概念已学'),
    ('02', 'Archetype、Chunk 与 Query', '已完成概念学习与两次 Query 筛选、组件读写实验。', '实践已完成'),
    ('03', 'Burst 与 SIMD', '原始 IJob 的指定配置已观察到 SIMD；性能未测量。', '生成代码已观察'),
    ('04', 'Job System', '已完成基础调度与依赖汇合实验；接下来学习 ECS System 的依赖。', '依赖实践已完成'),
]


def route_grid():
    return '<div class="route-grid">' + ''.join(f'<a class="route-item" href="/learning/#route-{num}"><div class="route-num"><span>PART {num}</span><span class="status">{state}</span></div><h3>{title}</h3><p>{description}</p></a>' for num,title,description,state in ROUTES) + '</div>'


def diagram():
    return '''<div class="study-art" role="img" aria-label="数据组成结构，观察连接理解：学习主题的抽象示意，不是性能测量。"><div class="art-caption"><span>IDEAS, INTO FOCUS.</span><span>01 / ∞</span></div><svg viewBox="0 0 440 235" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><g stroke="#b7c8ef" stroke-dasharray="3 7"><path d="M35 178 217 72 405 181M85 207 267 101M34 128 220 235M136 25 405 181"/></g><ellipse cx="220" cy="192" rx="151" ry="25" fill="#e5ebfa"/><path d="m78 144 48-28 48 28-48 28Z" fill="#afc4f1"/><path d="m78 144 48 28v42l-48-28Z" fill="#7d9ddf"/><path d="m126 172 48-28v42l-48 28Z" fill="#587cc5"/><path d="m172 96 49-28 49 28-49 29Z" fill="#7196e2"/><path d="m172 96 49 29v68l-49-29Z" fill="#4269b7"/><path d="m221 125 49-29v68l-49 29Z" fill="#2c4d92"/><path d="m270 137 48-28 48 28-48 28Z" fill="#d7e1f9"/><path d="m270 137 48 28v40l-48-28Z" fill="#acc1ec"/><path d="m318 165 48-28v40l-48 28Z" fill="#87a2d9"/><g stroke="#315aa3" stroke-width="1.5"><path d="M221 53V30h73"/><circle cx="221" cy="53" r="4" fill="#315aa3"/><path d="M76 125H45V79h38"/></g><g fill="#49628e" font-family="ui-monospace,monospace" font-size="10" letter-spacing="1"><text x="303" y="34">UNDERSTAND</text><text x="44" y="68">OBSERVE</text></g><circle cx="379" cy="74" r="5" fill="#d1a45d"/><path d="M365 74h-17m31-14v-9" stroke="#d1a45d"/></svg><div class="art-foot"><span>观察 · 实验 · 理解</span><span>UNITY FIELD NOTES</span></div></div>'''


def meta(post):
    state = '学习笔记' if post['status'] == 'completed' else '阅读中'
    kind = '' if post['status'] == 'completed' else ' reading'
    return f'<div class="post-meta"><span class="pill{kind}">{state}</span><time datetime="{post["date"]}">{post["date"].replace("-", ".")}</time><span>{post["read_minutes"]} 分钟阅读</span></div>'


def tags(post):
    return '<div class="tags">' + ''.join(f'<span class="tag">{esc(t)}</span>' for t in post['tags'][:3]) + '</div>'


def feature(post):
    if post.get('visual') == 'job-dependencies':
        return f'''<article class="feature"><div class="feature-copy">{meta(post)}<h3><a href="{post['permalink']}">{esc(post.get('short_title', post['title']))}</a></h3><p>{esc(post['excerpt'])}</p><div class="feature-bottom">{tags(post)}<a class="read-link" href="{post['permalink']}">阅读全文 →</a></div></div><div class="feature-visual" aria-label="A 和 C 独立，D 依赖两者；八项位移结果正确，未测量实际并行或速度。"><div class="code-label"><span>JOB DEPENDENCIES</span><span>05</span></div><pre class="decor-code"><span class="comment">// 两个条件都满足，D 才能开始</span>
A ──┐
    ├── D ── Complete()
C ──┘

<span class="value">PASS: 8/8</span></pre><div class="code-bottom"><span>依赖实践已完成 · 性能未测</span><span>NEXT: ECS DEPENDENCY</span></div></div></article>'''
    if post.get('visual') == 'burst-jobs':
        return f'''<article class="feature"><div class="feature-copy">{meta(post)}<h3><a href="{post['permalink']}">{esc(post.get('short_title', post['title']))}</a></h3><p>{esc(post['excerpt'])}</p><div class="feature-bottom">{tags(post)}<a class="read-link" href="{post['permalink']}">阅读全文 →</a></div></div><div class="feature-visual" aria-label="三种执行方式均通过 1024 项数值校验；原始 IJob 的指定 Inspector 配置观察到 SIMD。不是性能测试。"><div class="code-label"><span>BURST / SIMD / JOBS</span><span>04</span></div><pre class="decor-code"><span class="comment">// 三次正确性验证，不是速度排名</span>
IJob.Run()              PASS
IJob.Schedule()        PASS
IJobFor.ScheduleParallel()
                       PASS
<span class="comment">// 原始 IJob 的 Inspector</span>
vaddps ymm   →   8 floats</pre><div class="code-bottom"><span>数值通过 · 向量化有条件 · 性能未测</span><span>NEXT: BURST / DEPENDENCIES</span></div></div></article>'''
    if post.get('visual') == 'ecs-query-practice':
        return f'''<article class="feature"><div class="feature-copy">{meta(post)}<h3><a href="{post['permalink']}">{esc(post.get('short_title', post['title']))}</a></h3><p>{esc(post['excerpt'])}</p><div class="feature-bottom">{tags(post)}<a class="read-link" href="{post['permalink']}">阅读全文 →</a></div></div><div class="feature-visual" aria-label="Query 两次实际运行结果：保留 Frozen 排除条件匹配两个实体，移除后匹配三个。"><div class="code-label"><span>ECS / QUERY EXPERIMENT</span><span>03</span></div><pre class="decor-code"><span class="comment">// 两次 Console 输出，预测与实测一致</span>
<span class="key">WithNone</span>  Frozen  <span class="value">2 matches</span>
A=1  B=2  C=0  D=0

<span class="key">Without</span>   filter  <span class="value">3 matches</span>
A=1  B=2  C=0  D=3</pre><div class="code-bottom"><span>两次运行已验证 · 非性能测试</span><span>NEXT: BURST / SIMD</span></div></div></article>'''
    if post.get('visual') == 'ecs-query':
        return f'''<article class="feature"><div class="feature-copy">{meta(post)}<h3><a href="{post['permalink']}">{esc(post.get('short_title', post['title']))}</a></h3><p>{esc(post['excerpt'])}</p><div class="feature-bottom">{tags(post)}<a class="read-link" href="{post['permalink']}">阅读全文 →</a></div></div><div class="feature-visual" aria-label="Query 概念示意：条件匹配多个 Archetype，再遍历 Chunk，读取速度并写入位置。未运行代码实验。"><div class="code-label"><span>ECS / QUERY NOTES</span><span>02</span></div><pre class="decor-code"><span class="comment">// 筛选与访问，各司其职</span>
<span class="key">All</span>    Position + Velocity
<span class="key">Match</span>  Archetypes → Chunks

<span class="key">Read</span>   Velocity  <span class="value">RefRO</span>
<span class="key">Write</span>  Position  <span class="value">RefRW</span></pre><div class="code-bottom"><span>概念已学 · 代码实践待做</span><span>NEXT: PRACTICE</span></div></div></article>'''
    if post.get('visual') == 'ecs-layout':
        return f'''<article class="feature"><div class="feature-copy">{meta(post)}<h3><a href="{post['permalink']}">{esc(post.get('short_title', post['title']))}</a></h3><p>{esc(post['excerpt'])}</p><div class="feature-bottom">{tags(post)}<a class="read-link" href="{post['permalink']}">阅读全文 <span aria-hidden="true"><svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></span></a></div></div><div class="feature-visual" aria-label="组件数组概念示意：Position 与 Health 分别成数组，相同索引对应同一实体。概念阅读，未运行性能基准。"><div class="code-label"><span>ECS / CONCEPT NOTES</span><span>01</span></div><pre class="decor-code"><span class="comment">// 同一索引，同一个实体</span>
<span class="key">Entity</span>    [A] [B] [C] [D]
<span class="key">Position</span>  [A] [B] [C] [D]
<span class="key">Health</span>    [A] [B] [C] [D]

<span class="value">B + Armor</span> → 迁移与补洞</pre><div class="code-bottom"><span>概念阅读 · 尚未性能测量</span><span>NEXT: QUERY</span></div></div></article>'''
    return f'''<article class="feature"><div class="feature-copy">{meta(post)}<h3><a href="{post['permalink']}">{esc(post.get('short_title', post['title']))}</a></h3><p>{esc(post['excerpt'])}</p><div class="feature-bottom">{tags(post)}<a class="read-link" href="{post['permalink']}">阅读全文 <span aria-hidden="true"><svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></span></a></div></div><div class="feature-visual" aria-label="真实计数实验摘要：固定步长 0.02 秒，30 FPS 时每帧平均 1.667 步，82.4 FPS 时平均 0.607 步。"><div class="code-label"><span>FIXED STEP / EXPERIMENT</span><span>01—02</span></div><pre class="decor-code"><span class="comment">// 同样的步长，不同的渲染帧率</span>
<span class="key">fixedDeltaTime</span>  <span class="value">0.02 s</span>

<span class="key">30.0 FPS</span>  →  <span class="value">1.667</span> steps / frame
<span class="key">82.4 FPS</span>  →  <span class="value">0.607</span> steps / frame</pre><div class="code-bottom"><span>实测记录 · 每组 5.00 s</span><span>50.0 steps / s</span></div></div></article>'''


def home(posts):
    from starfield import render
    write('index.html', page('', render(posts), active='home'))


def toc_markup(headings):
    return '<ol class="toc">' + ''.join(f'<li><a href="#{anchor}">{esc(re.sub(r"[`*]", "", label))}</a></li>' for level,label,anchor in headings if level == 2) + '</ol>'


def support_panel():
    return '''<section class="article-support" aria-label="赞赏作者"><p>如果这篇记录对你有帮助，可以自愿赞赏支持。</p><details class="donation-panel" id="donation-panel"><summary>赞赏</summary><div class="donation-content"><p class="donation-note">选择微信或支付宝扫码，金额自定。付款前请在支付应用中核对收款人。</p><div class="donation-codes"><figure><figcaption>微信</figcaption><a href="/assets/donation-wechat.png" aria-label="查看微信收款码原图"><img src="/assets/donation-wechat.png" width="1280" height="1745" alt="微信收款二维码" loading="lazy" decoding="async"></a><a class="qr-original" href="/assets/donation-wechat.png" download>保存微信原图</a></figure><figure><figcaption>支付宝</figcaption><a href="/assets/donation-alipay.jpg" aria-label="查看支付宝收款码原图"><img src="/assets/donation-alipay.jpg" width="1170" height="1755" alt="支付宝收款二维码" loading="lazy" decoding="async"></a><a class="qr-original" href="/assets/donation-alipay.jpg" download>保存支付宝原图</a></figure></div><p class="donation-note">手机上可保存原图，再使用对应支付应用的相册识码功能。本站仅展示收款码，不处理付款，也不确认到账。</p><button class="donation-close" type="button" hidden>收起收款码</button></div></details></section>'''


def article(post):
    rendered, headings = markdown((SOURCE/'posts'/post['file']).read_text(encoding='utf-8'))
    toc = toc_markup(headings)
    notice = '' if post['status'] == 'completed' else '<div class="reading-notice"><strong>阅读进行中</strong><span>这篇记录的是当前阅读与待验证的问题，还不是已完成的实验结论。</span></div>'
    body = f'''<header class="page-head"><a class="eyebrow" href="/archives/">← UNITY / LEARNING NOTES</a><h1>{esc(post['title'])}</h1><p>{esc(post['excerpt'])}</p>{meta(post)}<div class="article-views" id="article-views" hidden><span id="busuanzi_container_page_pv" style="display:none">浏览 <span id="busuanzi_value_page_pv"></span> 次</span><small>由不蒜子提供</small></div></header><div class="article-layout"><article class="article-body" aria-label="文章正文"><details class="mobile-toc"><summary>本篇目录</summary>{toc}</details>{notice}{rendered}{support_panel()}<div class="article-end"><a href="/archives/">← 所有文章</a><a href="/learning/">下一站：ECS 学习路线 <svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></a></div></article><aside class="article-aside" aria-label="文章目录"><p class="aside-heading">ON THIS PAGE / 本篇目录</p>{toc}<div class="aside-note"><strong>把结论放回条件里。</strong>实测、推演与计划分开记录。<br>看见现象，也说明它的边界。</div><div class="aside-note">{tags(post)}</div></aside></div>'''
    write(post['permalink'].strip('/')+'/index.html',page(post['title'],body,post['permalink'],'archives',post['excerpt'],post))


def archives(posts):
    rows = []
    for post in posts:
        search = ' '.join([post['title'],post['excerpt'],*post['tags']])
        rows.append(f'<article class="archive-row" data-search="{esc(search)}"><time class="archive-date" datetime="{post["date"]}">{post["date"].replace("-", ".")}</time><div><span class="pill">{"学习笔记" if post["status"] == "completed" else "阅读中"}</span><h2><a href="{post["permalink"]}">{esc(post["title"])}</a></h2><p>{esc(post["excerpt"])}</p>{tags(post)}</div></article>')
    body = f'''<header class="page-head"><div class="eyebrow">THE NOTEBOOK</div><h1>每一次理解，都留个记录。</h1><p>把问题、证据和暂时的答案放在一起，方便回头再看。</p></header><div class="archive-toolbar"><span id="archive-count" class="archive-count" role="status">{len(posts)} 篇文章</span><label class="search-box"><span class="skip">搜索标题、摘要或标签</span><input id="archive-search" type="search" placeholder="搜索标题、摘要或标签" aria-label="搜索文章" autocomplete="off"></label></div><div class="archive-list">{''.join(rows)}<p class="empty-result" id="empty-result" hidden>暂时没有匹配的文章。试试“Unity”或“插值”。</p></div>'''
    write('archives/index.html',page('文章归档',body,'/archives/','archives'))


def learning(posts):
    first_link = next((p['permalink'] for p in posts if p['file'] == 'unity-fixed-timestep-interpolation.md'), '/archives/')
    ecs_link = next((p['permalink'] for p in posts if p['file'] == 'unity-ecs-cache-archetype-chunk.md'), '/archives/')
    body = f'''<header class="page-head"><div class="eyebrow">LEARNING ROADMAP</div><h1>带着问题，往底层走。</h1><p>物理前两课之后，沿着数据布局、编译优化和多线程这条线，继续理解 Unity ECS。</p></header><section class="route-page" aria-label="ECS 学习路线">{route_grid()}<div class="reading-notice"><strong>进度说明</strong><span>已完成缓存局部性、数据布局、Archetype / Chunk、结构迁移与 Query 筛选遍历的概念阅读和理解检查。已安装 Entities 1.5.0 并完成两次 Query 筛选与组件读写实验；已在原始 IJob 的指定 Inspector 配置观察到 SIMD，并完成 Run、Schedule、ScheduleParallel 的数值校验。已完成多任务依赖汇合实验，八项位移校验通过；尚未运行性能基准。</span></div><section class="route-detail" id="foundation"><span class="number">00</span><div><span class="pill">前两课已完成</span><h2>物理基础：固定时间步与插值</h2><p>完成 FixedUpdate 计数实验，以及插值与外推的阅读、数值推演。运动物体的插值对照实验仍待实践。</p><a class="read-link" href="{first_link}">阅读学习记录 <svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></a></div></section><section class="route-detail" id="route-01"><span class="number">01</span><div><span class="pill">概念阅读已完成</span><h2>数据布局与 CPU 缓存</h2><p>已理清缓存行、引用数组与结构体数组、AoS / SoA，以及访问方式与布局的关系。</p><p><a class="read-link" href="{ecs_link}">阅读 ECS 第一篇学习记录</a></p><ul><li>连续数据与分散对象，怎样影响缓存命中与遍历？</li><li>AoS、SoA 与组件数组分别描述什么？</li><li>数据布局带来的收益，为什么不等同于 SIMD 或多线程？</li></ul><p>阅读入口：<a class="read-link" href="https://docs.unity3d.com/Packages/com.unity.entities@1.5/manual/concepts-archetypes.html">Unity Entities 1.5 · Archetype concepts <svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></a></p><p>本阶段完成概念阅读与理解检查，尚未做性能对照实验。随后已安装 Entities 1.5.0，并在 Query 实践中完成两次运行。</p></div></section><section class="route-detail" id="route-02"><span class="number">02</span><div><span class="pill reading">Query 概念与基础实践已完成</span><h2>Archetype、Chunk 与查询</h2><p><a class="read-link" href="/2026/10/20/unity-ecs-query-traversal/">阅读 Query 概念记录</a> · <a class="read-link" href="/2026/10/22/unity-ecs-query-practice/">阅读两次 Query 实验记录</a></p><p>已理解分组与迁移，并完成 Query 类型条件、All / Any / None、Chunk 遍历与 RefRO / RefRW 的概念学习。普通字段值更新不改变组件类型组合。</p><ul><li>相同组件组合的实体如何分组与存储？</li><li>Query 如何筛选需要处理的数据？</li><li>添加或删除组件时，结构变化会带来哪些成本？</li></ul></div></section><section class="route-detail" id="route-03"><span class="number">03</span><div><span class="pill">基础学习与汇编观察已完成</span><h2>Burst 与 SIMD</h2><p>原始 IJob 在 Safety Check Off、Target Auto 配置下已观察到 vaddps 与循环展开；这不等于性能提升，也不是 IJobFor 的向量化证据。</p><p><a class="read-link" href="/2026/10/24/unity-burst-simd-jobs/">阅读 Burst 与 Job 实验记录</a></p><ul><li>哪些循环具备向量化条件？哪些写法会阻碍它？</li><li>Burst 编译优化与 SIMD 指令是什么关系？</li><li>怎样用 Burst Inspector 验证，而不是只看代码长相？</li></ul></div></section><section class="route-detail" id="route-04"><span class="number">04</span><div><span class="pill reading">基础调度与依赖实践已完成</span><h2>Job System 与依赖</h2><p><a class="read-link" href="/2026/10/27/unity-job-dependencies/">阅读 Job 依赖与八项位移实验</a></p><p>已跑通 IJob.Run、IJob.Schedule + Complete、IJobFor.ScheduleParallel + Complete；已理解独立索引、数据竞争和归约思路。已完成 A、C 独立调度后汇合到 D 的八项位移实验。实际工作线程数与加速幅度未测量；下一步学习 ECS System 的 Dependency。</p><ul><li>任务如何拆分？读写依赖如何表达？</li><li>什么时候必须同步，什么时候可以继续做别的工作？</li><li>如何区分数据布局、Burst 和多线程各自的贡献？</li></ul></div></section></section>'''
    write('learning/index.html',page('学习路线',body,'/learning/','learning'))


def support_pages():
    body = '''<header class="page-head"><div class="eyebrow">ABOUT THIS NOTEBOOK</div><h1>关于这本学习手记。</h1></header><div class="simple-content"><p>这里记录 Forgoi 的 Unity 学习过程：读过的资料、真正运行过的实验、卡住的问题，以及一步步建立起来的理解。</p><p>内容从物理更新与渲染开始，当前关注 ECS、数据布局、Burst / SIMD 和 Job System。完成的实验、阅读推演和未来计划会分别说明，避免把“看懂了”写成“已经验证”。</p><p>这个站点是轻量静态博客。文章保留为 Markdown，用 Python 标准库生成页面，托管在 GitHub Pages；没有统计脚本，也不依赖外部字体服务。</p><p><a href="https://github.com/Forgoi/Forgoi.github.io">查看源码和文章历史 <svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></a></p></div>'''
    write('about/index.html',page('关于本站',body,'/about/'))
    write('404.html',page('页面未找到','<section class="error-page"><div class="eyebrow">404 / LOST IN THE NOTEBOOK</div><h1>这一页还没写到。</h1><p>链接可能已失效，或者文章已经整理到了别处。</p><a class="button-link" href="/">回到首页 <svg class="outbound-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 12 12 4M4 4h8v8"/></svg></a></section>','/404.html'))


def feeds(posts):
    urls = ['/', '/archives/', '/learning/', '/about/'] + [p['permalink'] for p in posts]
    sitemap = '<?xml version="1.0" encoding="utf-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{xml_escape(BASE+u)}</loc></url>' for u in urls) + '</urlset>\n'
    write('sitemap.xml', sitemap)
    write('robots.txt', f'User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n')
    updated = max((p['date'] for p in posts), default='2026-10-19')+'T00:00:00Z'
    entries = ''.join(f'<entry><title>{xml_escape(p["title"])}</title><link href="{BASE+p["permalink"]}"/><id>{BASE+p["permalink"]}</id><updated>{p["date"]}T00:00:00Z</updated><summary>{xml_escape(p["excerpt"])}</summary></entry>' for p in posts)
    atom = f'<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="zh-CN"><title>Forgoi · Unity 学习手记</title><link href="{BASE}/atom.xml" rel="self"/><link href="{BASE}/"/><id>{BASE}/</id><updated>{updated}</updated><author><name>Forgoi</name></author>{entries}</feed>\n'
    write('atom.xml',atom)


def main():
    previous = ROOT/'.build-manifest.json'
    if previous.exists():
        for item in json.loads(previous.read_text(encoding='utf-8')):
            target = (ROOT/item).resolve()
            if ROOT not in target.parents or item.startswith(('blog-src/', 'scripts/', '.git/')):
                raise ValueError(f'Unsafe generated path: {item}')
            if target.is_file():
                target.unlink()
    posts = sorted(SITE['posts'], key=lambda p:p['date'], reverse=True)
    seen = set()
    for post in posts:
        path = post['permalink']
        if not re.fullmatch(r'/[a-z0-9/-]+/', path) or '..' in path or path in seen:
            raise ValueError(f'Invalid or duplicate permalink: {path}')
        seen.add(path)
        source_path = (SOURCE/'posts'/post['file']).resolve()
        if (SOURCE/'posts').resolve() not in source_path.parents:
            raise ValueError('Post source must remain inside blog-src/posts')
    for source in sorted((SOURCE/'static').iterdir()):
        write('assets/'+source.name,source.read_bytes())
    download_dir = SOURCE/'downloads'
    if download_dir.exists():
        for source in sorted(download_dir.iterdir()):
            write('downloads/'+source.name,source.read_text(encoding='utf-8'))
    write('.nojekyll', '')
    home(posts)
    archives(posts)
    learning(posts)
    for post in posts:
        article(post)
    support_pages()
    feeds(posts)
    previous.write_text(json.dumps(sorted(GENERATED),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Built {len(posts)} article(s), {len(GENERATED)} files. No build-time external dependencies.')

if __name__ == '__main__':
    main()
