from pathlib import Path
import pandas as pd
import re
from pypdf import PdfReader
from html import escape

pdf_path = Path('Gistda_Price_List.pdf')
base_name = pdf_path.stem

reader = PdfReader(str(pdf_path))
pages = []
for i, page in enumerate(reader.pages, 1):
    text = page.extract_text() or ''
    text = re.sub(r'\s+', ' ', text).strip()
    pages.append({'page': i, 'text': text})

if not pages:
    raise SystemExit('No text extracted from PDF')

df = pd.DataFrame(pages)

csv_path = Path(f'{base_name}.csv')
df.to_csv(csv_path, index=False, encoding='utf-8-sig')

xlsx_path = Path(f'{base_name}.xlsx')
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
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; vertical-align: top; }}
    th {{ background: #f3f3f3; }}
    pre {{ white-space: pre-wrap; word-break: break-word; margin: 0; }}
  </style>
</head>
<body>
  <h1>{base_name}</h1>
  <p>Exported from PDF using extracted text.</p>
  <table>
    <thead><tr><th>Page</th><th>Text</th></tr></thead>
    <tbody>{html_rows}</tbody>
  </table>
</body>
</html>
'''
html_path = Path(f'{base_name}.html')
html_path.write_text(html_content, encoding='utf-8')

print('Created:')
print(csv_path)
print(xlsx_path)
print(html_path)
