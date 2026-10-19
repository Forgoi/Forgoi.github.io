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

if __name__=='__main__':unittest.main()
