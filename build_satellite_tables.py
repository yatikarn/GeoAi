import re
from pathlib import Path
import pandas as pd
import urllib3
from pypdf import PdfReader
from html import escape

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

pdf_path = Path('Gistda_Price_List.pdf')
base_name = 'Gistda_Price_List_structured'

reader = PdfReader(str(pdf_path))
rows = []
current_section = ''

for page_no, page in enumerate(reader.pages, 1):
    text = page.extract_text() or ''
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if 'ราคาข้อมูลจากดาวเทียม' in line:
            current_section = line.replace('**', '').strip()
            continue

        # skip heading/footer noise
        if line.startswith('ฝ่ายพัฒนาธุรกิจ') or 'สอบถามรายละเอียดเพิ่มเติมได้ที่' in line:
            continue
        if line.startswith('หน่วย') or line.startswith('**ราคาดังกล่าว'):
            continue
        if line.startswith('ดาวเทียม') and '(' in line:
            continue
        if 'รายละเอียดภาพ' in line and '(' in line:
            continue
        if 'ข้อมูลในคลัง' in line and '(' in line:
            continue
        if 'ข้อมูลชนิดสั่งถ่าย' in line and '(' in line:
            continue
        if 'การติดตาม' in line and '(' in line:
            continue
        if 'Mode' in line and 'รายละเอียดภาพ' in line:
            continue

        # remove bullets
        cleaned = line.replace('•', '').replace('', '').strip()
        if not cleaned:
            continue

        tokens = cleaned.split()
        numeric_indices = [i for i, t in enumerate(tokens) if re.fullmatch(r'(\d[\d,\.]*|N/A)', t)]
        if len(numeric_indices) >= 2:
            archive_idx = numeric_indices[-2]
            tasking_idx = numeric_indices[-1]
            prefix_tokens = tokens[:archive_idx]
            if len(prefix_tokens) >= 2 and prefix_tokens[-1].endswith(('cm.', 'm.', 'km.')):
                resolution = ' '.join(prefix_tokens[-2:])
                satellite = ' '.join(prefix_tokens[:-2]).strip()
            elif len(prefix_tokens) >= 2 and re.fullmatch(r'\d[\d,\.]*', prefix_tokens[-1]):
                resolution = ' '.join(prefix_tokens[-1:])
                satellite = ' '.join(prefix_tokens[:-1]).strip()
            else:
                resolution = ' '.join(prefix_tokens[-1:]).strip() if prefix_tokens else ''
                satellite = ' '.join(prefix_tokens[:-1]).strip() if len(prefix_tokens) > 1 else ''

            archive_price = tokens[archive_idx]
            tasking_price = tokens[tasking_idx]
            if satellite and resolution and (archive_price != 'N/A' or tasking_price != 'N/A'):
                rows.append({
                    'section': current_section,
                    'page': page_no,
                    'satellite': satellite,
                    'resolution': resolution,
                    'archive_price': archive_price,
                    'tasking_price': tasking_price,
                })

# clean up and normalize
if rows:
    df = pd.DataFrame(rows)
    df['archive_price'] = df['archive_price'].replace({'N/A': ''})
    df['tasking_price'] = df['tasking_price'].replace({'N/A': ''})
    df['satellite'] = df['satellite'].str.replace(r'\s+', ' ', regex=True).str.strip()
    df['resolution'] = df['resolution'].str.replace(r'\s+', ' ', regex=True).str.strip()
    df['section'] = df['section'].fillna('')
else:
    df = pd.DataFrame(columns=['section', 'page', 'satellite', 'resolution', 'archive_price', 'tasking_price'])

csv_path = Path(f'{base_name}.csv')
xlsx_path = Path(f'{base_name}.xlsx')
html_path = Path(f'{base_name}.html')

df.to_csv(csv_path, index=False, encoding='utf-8-sig')
with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Satellite_Pricing', index=False)

html_rows = ''.join(
    f"<tr><td>{escape(str(r['section']))}</td><td>{escape(str(r['page']))}</td><td>{escape(str(r['satellite']))}</td><td>{escape(str(r['resolution']))}</td><td>{escape(str(r['archive_price']))}</td><td>{escape(str(r['tasking_price']))}</td></tr>"
    for _, r in df.iterrows()
)
html_content = f'''<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8" />
  <title>{base_name}</title>
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 24px; background: #f7f9fc; color: #1f2937; }}
    h1 {{ color: #123a5a; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #123a5a; color: white; }}
    tr:nth-child(even) td {{ background: #f9fafb; }}
  </style>
</head>
<body>
  <h1>ตารางราคาดาวเทียมแบบแยกตามประเภท</h1>
  <table>
    <thead>
      <tr>
        <th>ประเภท</th><th>หน้า</th><th>ดาวเทียม</th><th>ความละเอียด</th><th>Archive</th><th>Tasking</th>
      </tr>
    </thead>
    <tbody>{html_rows}</tbody>
  </table>
</body>
</html>
'''
html_path.write_text(html_content, encoding='utf-8')

print('Rows:', len(df))
print(csv_path)
print(xlsx_path)
print(html_path)
