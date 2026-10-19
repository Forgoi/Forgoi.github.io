#!/usr/bin/env python3
"""Validate generated pages, local links, metadata and deterministic output."""
import hashlib
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

class Document(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=set();self.refs=[];self.h1=0;self.lang=None;self.title=False;self.description=False;self.main=False;self.errors=[];self.resources=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:
            if attrs['id'] in self.ids:self.errors.append('duplicate id '+attrs['id'])
            self.ids.add(attrs['id'])
        if tag=='html':self.lang=attrs.get('lang')
        if tag=='h1':self.h1+=1
        if tag=='title':self.title=True
        if tag=='main':self.main=True
        if tag=='meta' and attrs.get('name')=='description':self.description=bool(attrs.get('content'))
        for name in ('href','src'):
            if name in attrs:self.refs.append(attrs[name])
        if tag in ('script','img','iframe','link'):
            resource=attrs.get('src') or (attrs.get('href') if attrs.get('rel')=='stylesheet' else '')
            if resource:self.resources.append(resource)


def hashes():
    paths=json.loads((ROOT/'.build-manifest.json').read_text())
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}


def main():
    before=hashes()
    subprocess.run([sys.executable,str(ROOT/'scripts/build.py')],check=True,cwd=ROOT)
    after=hashes()
    assert before==after,'Build is not deterministic or output was stale; build again and inspect.'
    documents={}
    for rel in after:
        if rel.endswith('.html'):
            doc=Document();doc.feed((ROOT/rel).read_text(encoding='utf-8'));documents[rel]=doc
    checked=0
    for rel,doc in documents.items():
        assert doc.h1==1,f'{rel}: expected one H1, got {doc.h1}'
        assert doc.lang=='zh-CN',f'{rel}: language missing'
        assert doc.title and doc.description and doc.main,f'{rel}: required metadata/landmarks missing'
        assert not doc.errors,f'{rel}: {doc.errors}'
        assert all(not r.startswith(('http:','https:','//')) for r in doc.resources),f'{rel}: external runtime resource'
        for ref in doc.refs:
            parts=urlsplit(ref)
            if parts.scheme or parts.netloc:continue
            path=unquote(parts.path)
            target=(ROOT/path.lstrip('/')) if path.startswith('/') else (ROOT/rel).parent/path
            if not path:target=ROOT/rel
            if target.is_dir():target=target/'index.html'
            assert target.is_file(),f'{rel}: broken link {ref}'
            if parts.fragment and target.suffix=='.html':
                target_rel=str(target.relative_to(ROOT))
                assert unquote(parts.fragment) in documents[target_rel].ids,f'{rel}: missing anchor {ref}'
            checked+=1
    ET.parse(ROOT/'sitemap.xml');ET.parse(ROOT/'atom.xml')
    site=json.loads((ROOT/'blog-src/site.json').read_text())
    for post in site['posts']:
        assert post['status'] in ('completed','reading'), 'Unknown article status'
        source=(ROOT/'blog-src/posts'/post['file']).read_text()
        assert source.count('```')%2==0,'Unbalanced source code fences'
    assert (ROOT/'.nojekyll').exists()
    assert not (ROOT/'2023').exists() and not (ROOT/'2024').exists(),'Retired posts still present'
    assert (ROOT/'downloads/FixedStepProbe.cs').read_bytes()==(ROOT/'blog-src/downloads/FixedStepProbe.cs').read_bytes()
    print(f'PASS: {len(documents)} HTML pages; {checked} local references/anchors; XML feeds; no third-party runtime resources; source download; deterministic {len(after)}-file rebuild.')

if __name__=='__main__':main()
