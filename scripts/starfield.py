"""Home-only knowledge constellation. Pure markup, no external dependencies."""
import html
import random

def render(posts):
    by_file = {p['file']: p for p in posts}
    records = [
        ('unity-fixed-timestep-interpolation.md', '时间步与渲染插值', 'TIME & SIMULATION', 'time', 17, 48),
        ('unity-ecs-cache-archetype-chunk.md', '数据布局与 Chunk', 'DATA-ORIENTED DESIGN', 'ecs', 45, 24),
        ('unity-ecs-query-traversal.md', 'Query 筛选与遍历', 'DATA-ORIENTED DESIGN', 'ecs', 55, 48),
        ('unity-ecs-query-practice.md', 'Query 读写实验', 'DATA-ORIENTED DESIGN', 'ecs', 43, 70),
        ('unity-burst-simd-jobs.md', 'Burst · SIMD · Jobs', 'PARALLEL COMPUTING', 'jobs', 78, 33),
        ('unity-job-dependencies.md', 'Job 依赖与汇合', 'PARALLEL COMPUTING', 'jobs', 87, 65),
        ('unity-ecs-system-dependency.md', 'System Dependency', 'PARALLEL COMPUTING', 'jobs', 65, 82),
        ('unity-ecs-entity-command-buffer.md', 'ECB 与结构变化', 'DATA-ORIENTED DESIGN', 'ecs', 26, 82),
    ]
    records = [r for r in records if r[0] in by_file]
    nodes = []
    for i, (file, title, group, color, x, y) in enumerate(records):
        p = by_file[file]
        nodes.append(f'''<a class="knowledge-star {color} is-lit" href="{p['permalink']}" style="--x:{x}%;--y:{y}%;--order:{i}" data-order="{i}" aria-label="已点亮：{title}，阅读学习记录"><span class="star-orbit" aria-hidden="true"></span><span class="star-core" aria-hidden="true"></span><span class="star-label"><strong>{title}</strong><small>{p['date'].replace('-', '.')} <span aria-hidden="true">↗</span></small></span></a>''')
    rng = random.Random(20261027)
    dust = ''.join(f'<circle cx="{rng.randrange(12,1188)}" cy="{rng.randrange(12,490)}" r="{rng.choice([.55,.7,.85,1.1])}" opacity="{rng.choice([.18,.23,.32,.48])}"/>' for _ in range(135))
    list_rows = []
    for i,(file,title,group,color,x,y) in enumerate(reversed(records)):
        p = by_file[file]
        list_rows.append(f'''<a class="orbit-note {color}" href="{p['permalink']}"><span class="note-star" aria-hidden="true">✧</span><span class="note-main"><small>{group}</small><strong>{html.escape(p['short_title'].replace(chr(10), ''))}</strong></span><time datetime="{p['date']}">{p['date'][5:].replace('-', '.')}</time><span class="note-arrow" aria-hidden="true">↗</span></a>''')
    return f'''<div class="space-intro"><div class="space-heading"><div class="space-eyebrow"><span></span> FORGOI'S KNOWLEDGE UNIVERSE</div><h1>每一次理解，<br>都让宇宙<span>亮一点。</span></h1><p>从一个问题出发，让零散的知识彼此连接。<br>这片星空，记录我走过的学习轨迹。</p></div><div class="voyage-log"><span class="log-kicker">EXPLORATION LOG / 001</span><div class="log-count"><strong>{len(records):02}</strong><span>篇学习记录已点亮<br><i>探索仍在继续</i></span></div><div class="log-rule"></div><span class="log-foot">UNITY · ECS · THE WAY THINGS WORK</span></div></div>
<section class="universe" aria-labelledby="map-title"><div class="map-toolbar"><h2 id="map-title"><span class="crosshair" aria-hidden="true">+</span> 我的知识星图 <small>KNOWLEDGE ATLAS</small></h2><div class="map-tools"><button id="replay-stars" type="button" hidden><span aria-hidden="true">↻</span> 重放点亮</button><a href="#knowledge-list">列表阅读 <span aria-hidden="true">↘</span></a></div></div>
<div class="star-map"><div class="map-mist mist-time" aria-hidden="true"></div><div class="map-mist mist-ecs" aria-hidden="true"></div><div class="map-mist mist-jobs" aria-hidden="true"></div><svg class="space-lines" viewBox="0 0 1200 500" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="route-light"><stop stop-color="#dcbd83" stop-opacity=".25"/><stop offset=".5" stop-color="#85d6db" stop-opacity=".65"/><stop offset="1" stop-color="#b0a0e1" stop-opacity=".25"/></linearGradient></defs><g fill="#d4e6fb">{dust}</g><g fill="none" stroke="#94b4d0" opacity=".08"><ellipse cx="550" cy="260" rx="565" ry="180" transform="rotate(-14 550 260)"/><ellipse cx="550" cy="260" rx="480" ry="145" transform="rotate(-14 550 260)"/><path d="M0 250h1200M600 0v500" stroke-dasharray="2 11"/></g><g class="constellation-lines" fill="none" stroke-width="1"><path class="time-line" d="M140 320 204 240 275 177" stroke="#d7b879" opacity=".23"/><path d="M540 120 660 240 516 350 540 120" stroke="#83cdd6" opacity=".45"/><path d="M936 165 1044 325" stroke="#b4a3e5" opacity=".5"/><path d="M204 240Q365 190 540 120M660 240Q790 280 936 165" stroke="url(#route-light)" stroke-dasharray="3 7" opacity=".45"/><path d="M660 240 780 410M1044 325 780 410" stroke="#8cabc5" stroke-dasharray="3 7" opacity=".17"/></g><g fill="none" stroke="#87a3be" opacity=".17"><circle cx="140" cy="320" r="2"/><circle cx="275" cy="177" r="2"/><circle cx="1100" cy="440" r="2"/><path d="M1030 445h50M1055 420v50"/></g></svg>
<div class="region-label region-time"><small>SECTOR 01</small><h3>时间与模拟</h3><span>TIME & SIMULATION</span></div><div class="region-label region-ecs"><small>SECTOR 02</small><h3>数据与实体</h3><span>DATA-ORIENTED DESIGN</span></div><div class="region-label region-jobs"><small>SECTOR 03</small><h3>编译与并行</h3><span>PARALLEL COMPUTING</span></div>
{''.join(nodes)}
<a class="knowledge-star in-progress" href="#current-focus" style="--x:23%;--y:24%" aria-label="正在探索：ECS 性能底层，查看当前进度"><span class="star-orbit" aria-hidden="true"></span><span class="star-core" aria-hidden="true"></span><span class="star-label"><strong>ECS 性能底层</strong><small>正在探索 · 尚未点亮</small></span></a>
<div class="unexplored"><span>· · ·</span> 未探索区域</div><span class="map-coordinate" aria-hidden="true">RA 06h 27m / DEC +20°</span></div>
<div class="map-bottom"><div class="star-legend"><span><i class="legend-lit"></i>已点亮</span><span><i class="legend-active"></i>探索中</span><span><i class="legend-dark"></i>未探索</span></div><p>一颗亮星 = 一篇已完成的学习记录 <span>·</span> 点击星点，回到当时的理解</p></div><p id="replay-status" class="visually-hidden" aria-live="polite"></p></section>
<section class="current-focus" id="current-focus" aria-labelledby="focus-title"><div class="focus-symbol" aria-hidden="true"><span></span>✧</div><div class="focus-copy"><div class="focus-eyebrow">NOW EXPLORING <span>正在探索</span></div><h2 id="focus-title">数据怎样搬运，才能让计算跑得更快？</h2><p>ECS 性能底层：开始探索缓存有效数据、预取与内存带宽；本课尚未完成。</p></div><a class="focus-link" href="/learning/#route-01">查看学习路线 <span aria-hidden="true">↗</span></a></section>
<section class="space-records" id="knowledge-list" aria-labelledby="record-title"><div class="records-heading"><div><span class="space-eyebrow">SIGNALS FROM THE JOURNEY</span><h2 id="record-title">从星光，回到文字。</h2></div><a href="/archives/">所有学习手记 <span aria-hidden="true">↗</span></a></div><div class="orbit-notes">{''.join(list_rows)}</div></section><div class="space-closing"><span aria-hidden="true">✦</span><p>宇宙很大。不必一次照亮。<br><strong>下一次理解，就是下一束光。</strong></p><small>KEEP ASKING. KEEP EXPLORING.</small></div>'''
