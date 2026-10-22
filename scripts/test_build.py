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
        self.assertEqual(post['file'], 'unity-ecs-query-practice.md')
        content = build.feature(post)
        self.assertIn('ECS / QUERY EXPERIMENT', content)
        self.assertIn('两次运行已验证 · 非性能测试', content)
        self.assertIn('A=1  B=2  C=0  D=3', content)
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
        self.assertNotIn('尚未运行 ECS 示例', content)
        self.assertNotIn('Query 是下一步', content)
        self.assertNotIn('ECS 系列刚开始阅读', content)

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
