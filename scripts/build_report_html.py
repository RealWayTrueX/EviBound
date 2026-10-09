#!/usr/bin/env python3
"""Offline report text and embedded measured figure; evidence links stay relative."""
import base64
import html
from pathlib import Path
import re
import markdown

STYLE='''body{font:17px/1.8 system-ui,"Noto Sans CJK SC",sans-serif;margin:0;color:#173042;background:#f2f5f7}main{max-width:1120px;margin:40px auto;padding:44px 52px;background:white;border-top:6px solid #087f8c}h1{font-size:32px;line-height:1.35}h2{margin-top:2em;border-bottom:1px solid #d5e0e6;padding-bottom:.35em}a{color:#087487}table{border-collapse:collapse;font-size:14px;width:100%;margin:24px 0;display:block;overflow-x:auto}th,td{padding:9px 12px;border-bottom:1px solid #d5e0e6;text-align:left}th{background:#e9f1f4}img{width:100%;height:auto}pre{overflow-x:auto;padding:18px;background:#f1f5f8}code{font-size:.9em}strong{color:#0b5363}.note{font-size:14px;color:#526674}@media(max-width:700px){main{margin:0;padding:20px}h1{font-size:25px}}@media print{body{background:white}main{padding:0;margin:0;max-width:none}a{color:inherit}h2{break-after:avoid}tr,img{break-inside:avoid}}'''
for language in ('zh-CN','en'):
    source=Path(f'reports/feasibility.{language}.md')
    body=markdown.markdown(source.read_text(),extensions=['tables','fenced_code','toc'])
    def embed(match):
        path=source.parent/match.group(1)
        if not path.exists():return match.group(0)
        return 'src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'"'
    body=re.sub(r'src="([^"]+\.png)"',embed,body)
    title='EviBound 可行性实验报告' if language=='zh-CN' else 'EviBound feasibility findings'
    result=f'<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main>{body}<p class="note">Offline text and embedded figures. Linked evidence remains in the project directory.</p></main></body></html>'
    source.with_suffix('.html').write_text(result)
    print(source.with_suffix('.html'))
