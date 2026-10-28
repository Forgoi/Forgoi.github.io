import unittest
from unittest.mock import patch
import build

class StarfieldTests(unittest.TestCase):
    def markup(self):
        with patch.object(build,'write') as write:
            build.home(build.SITE['posts'])
        return write.call_args.args[1]
    def test_home_only(self):
        home=self.markup()
        self.assertIn('class="cosmic-home"',home)
        self.assertIn('/assets/starfield.css',home)
        self.assertIn('content="dark"',home)
        article=build.page('Article','content',active='archives')
        self.assertNotIn('cosmic-home',article)
        self.assertNotIn('/assets/starfield.css',article)
        self.assertIn('content="light"',article)
    def test_progress_truth(self):
        home=self.markup()
        self.assertEqual(home.count('data-order='),6)
        self.assertEqual(home.count('class="knowledge-star in-progress"'),1)
        self.assertIn('正在探索 · 尚未点亮',home)
        for post in build.SITE['posts']:
            self.assertIn(post['permalink'],home)
        self.assertIn('一颗亮星 = 一篇已完成的学习记录',home)
        self.assertNotIn('100%',home)
    def test_accessible_and_nojs(self):
        home=self.markup()
        self.assertIn('id="replay-stars" type="button" hidden',home)
        self.assertIn('aria-live="polite"',home)
        self.assertIn('id="knowledge-list"',home)
        self.assertIn('aria-label="已点亮',home)
        self.assertIn('prefers-reduced-motion',(build.SOURCE/'static'/'starfield.css').read_text())

if __name__=='__main__':unittest.main()
