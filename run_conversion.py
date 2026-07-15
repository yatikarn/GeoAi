import os
import requests
from pathlib import Path
from pypdf import PdfReader
import pandas as pd
from html import escape
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = 'https://www.gistda.or.th/download/Gistda_Price_List.pdf'
pdf_path = Path('Gistda_Price_List.pdf')
base_name = pdf_path.stem

resp = requests.get(url, timeout=60, verify=False)
resp.raise_for_status()
pdf_path.write_bytes(resp.content)
print('Downloaded', pdf_path, pdf_path.stat().st_size)

reader = PdfReader(str(pdf_path))
pages = []
for i, page in enumerate(reader.pages, 1):
    text = page.extract_text() or ''
    text = re.sub(r'\s+', ' ', text).strip()
    pages.append({'page': i, 'text': text})

df = pd.DataFrame(pages)
print(df.head())

csv_path = Path(f'{base_name}.csv')
xlsx_path = Path(f'{base_name}.xlsx')
html_path = Path(f'{base_name}.html')

df.to_csv(csv_path, index=False, encoding='utf-8-sig')
with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Sheet1', index=False)

html_rows = ''.join(
    f'<tr><td>{page}</td><td><pre>{escape(text)}</pre></td></tr>'
    for page, text in zip(df['page'], df['text'])
)
html_content = f'''<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8" />
  <title>{base_name}</title>
</head>
<body>
  <h1>{base_name}</h1>
  <table>
    <tr><th>Page</th><th>Text</th></tr>
    {html_rows}
  </table>
</body>
</html>
'''
html_path.write_text(html_content, encoding='utf-8')

for path in [csv_path, xlsx_path, html_path]:
    print(path.name, path.exists(), path.stat().st_size if path.exists() else None)
