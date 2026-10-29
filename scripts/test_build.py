#!/usr/bin/env python3
import unittest
import build

class MarkdownTests(unittest.TestCase):
    def test_escape_html(self):
        self.assertEqual(build.inline('<script>alert(1)</script>'),'&lt;script&gt;alert(1)&lt;/script&gt;')
    def test_inline(self):
        value=build.inline('**强调** `a < b` [资料](https://example.com/)')
        self.assertIn('<strong>强调</strong>',value)
        self.assertIn('<code>a &lt; b</code>',value)
        self.assertIn('href="https://example.com/"',value)
    def test_disallow_active_urls(self):
        self.assertEqual(build.safe_url('javascript:alert(1)'),'#')
        self.assertEqual(build.safe_url('data:text/html,evil'),'#')
    def test_table(self):
        value,_=build.markdown('| 值 | 说明 |\n| --- | --- |\n| 50 | 每秒 |')
        self.assertIn('<table>',value)
        self.assertEqual(value.count('<th scope="col">'),2)
        self.assertIn('<td>50</td>',value)
    def test_code_preserved(self):
        value,_=build.markdown('```text\na < b && c > d\n  indent\n```')
        self.assertIn('a &lt; b &amp;&amp; c &gt; d\n  indent',value)
    def test_unclosed_code_fails(self):
        with self.assertRaises(ValueError):build.markdown('```\nmissing fence')
    def test_toc(self):
        value,toc=build.markdown('## 中文标题\n\n段落\n\n### 子标题')
        self.assertEqual(toc,[(2,'中文标题','section-1'),(3,'子标题','section-2')])
        self.assertIn('id="section-1"',value)
    def test_frontmatter_and_comments(self):
        value,_=build.markdown('---\ntitle: Test\n---\n\n<!-- more -->\n\n正文')
        self.assertEqual(value,'<p>正文</p>')
    def test_lists(self):
        value,_=build.markdown('- one\n- two\n\n1. first\n2. second')
        self.assertIn('<ul><li>one</li><li>two</li></ul>',value)
        self.assertIn('<ol><li>first</li><li>second</li></ol>',value)
    def test_highlight_does_not_change_text(self):
        from html.parser import HTMLParser
        class Text(HTMLParser):
            def __init__(self):super().__init__();self.out=''
            def handle_data(self,data):self.out+=data
        code='float dt = 0.02f; // a < b\nvar name = "hi";'
        p=Text();p.feed(build.highlighted(code,'csharp'))
        self.assertEqual(code,p.out)

class BlogContentTests(unittest.TestCase):
    def test_newest_feature_matches_article(self):
        post = build.SITE['posts'][0]
        self.assertEqual(post['file'], 'unity-ecs-system-dependency.md')
        content = build.feature(post)
        self.assertIn('ECS SYSTEM DEPENDENCY', content)
        self.assertIn('单实体一轮 · 性能未测', content)
        self.assertIn('PASS · dt=1', content)
        self.assertNotIn('FIXED STEP / EXPERIMENT', content)

    def test_learning_links_and_progress(self):
        from unittest.mock import patch
        with patch.object(build, 'write') as write:
            build.learning(build.SITE['posts'])
        content = write.call_args.args[1]
        self.assertIn('href="/2026/10/19/unity-fixed-timestep-interpolation/"', content)
        self.assertIn('href="/2026/10/19/unity-ecs-cache-archetype-chunk/"', content)
        self.assertIn('Query 概念与基础实践已完成', content)
        self.assertIn('href="/2026/10/20/unity-ecs-query-traversal/"', content)
        self.assertIn('href="/2026/10/22/unity-ecs-query-practice/"', content)
        self.assertIn('href="/2026/10/27/unity-job-dependencies/"', content)
        self.assertNotIn('多任务依赖仍待实践', content)
        self.assertNotIn('尚未运行 ECS 示例', content)
        self.assertNotIn('Query 是下一步', content)
        self.assertNotIn('ECS 系列刚开始阅读', content)

    def test_ecs_dependency_lesson_and_exact_download(self):
        import hashlib
        article = (build.SOURCE / 'posts' / 'unity-ecs-system-dependency.md').read_text()
        for term in ['不是多线程加速', '只有一个实体', '而非另外粘贴', 'CompleteDependencyBeforeRO<Position>', 'SystemState', '显式', '本课没有额外运行固定组实验', '正在学习']:
            self.assertIn(term, article)
        source = (build.SOURCE / 'downloads' / 'DependencyExperimentBootstrap.cs').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), 'e3d713ccd12796ea1a123a60b2cd428c182159206fdc083a3a5c8c79fe0c2fe3')
        self.assertEqual(source, (build.ROOT / 'downloads' / 'DependencyExperimentBootstrap.cs').read_bytes())

    def test_dependency_lesson_evidence(self):
        article = (build.SOURCE / 'posts' / 'unity-job-dependencies.md').read_text()
        for term in ['PASS: 8/8; displacement = 2, -4, 6, -8, 10, -12, 14, -16', '核心片段', '不能单独作为完整脚本运行', '不是性能基准', '没有 Profiler 时间线', '尚未完成', 'jobD.Schedule(ready)', 'CombineDependencies(handleA, handleC)']:
            self.assertIn(term, article)
        self.assertNotIn('/downloads/JobDependencyProbe.cs', article)

    def test_burst_jobs_evidence_and_download(self):
        article = (build.SOURCE / 'posts' / 'unity-burst-simd-jobs.md').read_text()
        for evidence in ['Safety Check Off', 'Target (Auto)', '1024/1024', '没有重新查看 IJobFor', '没有实际运行 1025', '不是性能基准', '归约']:
            self.assertIn(evidence, article)
        for name in ['BurstSimdProbe.cs', 'EcsQueryPractice.SceneScoped.cs']:
            self.assertEqual((build.SOURCE / 'downloads' / name).read_bytes(), (build.ROOT / 'downloads' / name).read_bytes())

    def test_query_practice_evidence_and_download(self):
        article = (build.SOURCE / 'posts' / 'unity-ecs-query-practice.md').read_text()
        self.assertIn('[Query实验] 本次匹配数量：2', article)
        self.assertIn('[Query实验] 本次匹配数量：3', article)
        self.assertIn('A=1，B=2，C=0，D=0', article)
        self.assertIn('A=1，B=2，C=0，D=3', article)
        self.assertIn('不是额外的运行结果', article)
        self.assertIn('没有验证 Jobs、Burst 或 SIMD', article)
        source = (build.SOURCE / 'downloads' / 'EcsQueryPractice.cs').read_bytes()
        self.assertEqual(source, (build.ROOT / 'downloads' / 'EcsQueryPractice.cs').read_bytes())
        self.assertIn(b'.WithNone<Frozen>()', source)


class FeatureTests(unittest.TestCase):
    def test_article_only_counter_and_donations(self):
        from unittest.mock import patch
        for post in build.SITE['posts']:
            with patch.object(build, 'write') as write:
                build.article(post)
            html = write.call_args.args[1]
            self.assertEqual(html.count('id="busuanzi_value_page_pv"'), 1)
            self.assertIn('id="article-views" hidden', html)
            self.assertIn('https://busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js', html)
            self.assertIn('<details class="donation-panel"', html)
            self.assertIn('微信收款二维码', html)
            self.assertIn('支付宝收款二维码', html)
            self.assertNotIn('giscus', html)
        html = build.page('Index', 'Test')
        self.assertNotIn('busuanzi', html)
        self.assertNotIn('donation-panel', html)

    def test_original_qr_bytes(self):
        import hashlib
        expected = {
            'donation-wechat.png': '2d44408e40896d65e43554a0cf04959030731c1e88d8f26eb7131c548ffff5bb',
            'donation-alipay.jpg': 'c9a44a09167e127a2287bf34f55800171e5f5d1b9349f6b7079b77be4fa2ff69',
        }
        for name, digest in expected.items():
            source = (build.SOURCE / 'static' / name).read_bytes()
            self.assertEqual(hashlib.sha256(source).hexdigest(), digest)
            self.assertEqual(source, (build.ROOT / 'assets' / name).read_bytes())

if __name__=='__main__':unittest.main()
