"""Download the GISTDA satellite price list PDF and extract structured price data.

Usage:
    python gistda_price_extractor.py [URL] [--outdir DIR]

Replaces the old run_conversion.py / build_satellite_tables.py pair. Those
scripts guessed table structure by splitting raw page text into word tokens,
which broke on rows with multi-number resolutions (e.g. "10 x 12 - 20 x 20
m."). This version reads the PDF's actual table/cell structure via
pdfplumber, which is far more robust.
"""
import argparse
import re
from html import escape
from pathlib import Path

import pandas as pd
import pdfplumber
import plotly.graph_objects as go
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_URL = 'https://www.gistda.or.th/download/Gistda_Price_List.pdf'

PRICE_RE = re.compile(r'^[\d,]+$')
RESOLUTION_RE = re.compile(r'.*\d.*(cm|m|km)\.?\s*$', re.IGNORECASE)
SUBGROUP_RE = re.compile(r'\([A-Za-z]+\s*band\)', re.IGNORECASE)
SECTION_RE = re.compile(
    r'ราคาข้อมูลจากดาวเทียม(?:(?!ดาวเทียม|หน่วย|Mode)[^()]){0,60}(?:\([^)]{0,60}\))?'
)
LABEL_KEYWORDS = [
    ('ในคลัง', 'Archive'), ('Archive', 'Archive'),
    ('สั่งถ่าย', 'Tasking'), ('Tasking', 'Tasking'),
    ('ติดตาม', 'Monitoring'), ('Monitoring', 'Monitoring'),
    ('Single Look', 'Single Look complex'),
    ('Path Image', 'Path Image'),
    ('New Acquisition', 'New Acquisition'),
]


def download_pdf(url: str, dest: Path) -> Path:
    resp = requests.get(url, timeout=60, verify=False)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def header_labels(texts):
    found = []
    for cell in texts:
        for kw, label in LABEL_KEYWORDS:
            if kw in cell and label not in found:
                found.append(label)
    return found


def extract_rows(pdf_path: Path) -> pd.DataFrame:
    rows = []
    current_section = ''
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            flat_text = re.sub(r'\s+', ' ', page.extract_text() or '').strip()
            m = SECTION_RE.search(flat_text)
            if m:
                current_section = m.group(0).strip()

            for table in page.extract_tables():
                header_texts = []
                labels = None
                current_subgroup = ''
                first_data_seen = False

                for raw_row in table:
                    cells = [(c or '').replace('\n', ' ').strip() for c in raw_row]
                    non_empty = [c for c in cells if c]
                    if not non_empty:
                        continue

                    if len(non_empty) == 1 and SUBGROUP_RE.search(non_empty[0]):
                        current_subgroup = non_empty[0]

                    price_idx = [
                        i for i, c in enumerate(non_empty)
                        if PRICE_RE.fullmatch(c) or c == 'N/A'
                    ]
                    if len(price_idx) < 2:
                        if not first_data_seen:
                            header_texts.extend(non_empty)
                        continue

                    first_data_seen = True
                    if labels is None:
                        labels = header_labels(header_texts)
                        while len(labels) < 2:
                            labels.append(f'Price {len(labels) + 1}')

                    res_idx = next(
                        (i for i, c in enumerate(non_empty) if RESOLUTION_RE.match(c)),
                        None,
                    )
                    if res_idx is None:
                        continue
                    resolution = non_empty[res_idx]

                    price1_i, price2_i = price_idx[-2], price_idx[-1]
                    price1 = non_empty[price1_i]
                    price2 = non_empty[price2_i]

                    name_cells = [
                        c for i, c in enumerate(non_empty)
                        if i not in (res_idx, price1_i, price2_i)
                    ]
                    deduped = []
                    for c in name_cells:
                        if not deduped or deduped[-1] != c:
                            deduped.append(c)
                    name = ' '.join(deduped).strip()
                    if not name:
                        continue
                    if current_subgroup:
                        name = f'{current_subgroup} - {name}'

                    rows.append({
                        'section': current_section,
                        'page': page_no,
                        'name': name,
                        'resolution': resolution,
                        'price_1_label': labels[0],
                        'price_1': None if price1 == 'N/A' else price1,
                        'price_2_label': labels[1],
                        'price_2': None if price2 == 'N/A' else price2,
                    })

    return pd.DataFrame(rows, columns=[
        'section', 'page', 'name', 'resolution',
        'price_1_label', 'price_1', 'price_2_label', 'price_2',
    ])


def write_outputs(df: pd.DataFrame, base_name: str, outdir: Path):
    csv_path = outdir / f'{base_name}.csv'
    xlsx_path = outdir / f'{base_name}.xlsx'
    html_path = outdir / f'{base_name}.html'

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Satellite_Pricing', index=False)

    html_rows = ''.join(
        '<tr>' + ''.join(f'<td>{escape(str(v)) if pd.notna(v) else ""}</td>' for v in row) + '</tr>'
        for row in df.itertuples(index=False)
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
  <h1>ตารางราคาดาวเทียม (ทุกหมวด)</h1>
  <table>
    <thead>
      <tr>{''.join(f'<th>{escape(c)}</th>' for c in df.columns)}</tr>
    </thead>
    <tbody>{html_rows}</tbody>
  </table>
</body>
</html>
'''
    html_path.write_text(html_content, encoding='utf-8')
    return csv_path, xlsx_path, html_path


def to_number(series):
    return pd.to_numeric(series.astype(str).str.replace(',', ''), errors='coerce')


def build_comparison_chart(df: pd.DataFrame, out_path: Path):
    optical = df[(df['page'] <= 4) & df['price_1'].notna() & df['price_2'].notna()].copy()
    optical['archive'] = to_number(optical['price_1'])
    optical['tasking'] = to_number(optical['price_2'])
    optical = optical.dropna(subset=['archive', 'tasking']).sort_values('archive', ascending=False)

    fig = go.Figure()
    fig.add_bar(name='Archive', x=optical['name'], y=optical['archive'])
    fig.add_bar(name='Tasking', x=optical['name'], y=optical['tasking'])
    fig.update_layout(
        title='เปรียบเทียบราคาข้อมูลดาวเทียม: Archive vs Tasking (บาท/ตร.กม.)',
        xaxis_title='ดาวเทียม',
        yaxis_title='ราคา (บาท)',
        barmode='group',
        template='plotly_white',
    )
    fig.write_html(out_path, include_plotlyjs='cdn')
    return optical[['name', 'resolution', 'archive', 'tasking']], out_path


def main():
    parser = argparse.ArgumentParser(description='Extract GISTDA satellite price list into structured data.')
    parser.add_argument('url', nargs='?', default=DEFAULT_URL, help='PDF URL to download')
    parser.add_argument('--outdir', default='.', help='Output directory')
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    pdf_path = download_pdf(args.url, outdir / 'Gistda_Price_List.pdf')
    print('Downloaded', pdf_path, pdf_path.stat().st_size, 'bytes')

    df = extract_rows(pdf_path)
    print('Extracted', len(df), 'rows')

    csv_path, xlsx_path, html_path = write_outputs(df, 'Gistda_Price_List_structured', outdir)
    for p in (csv_path, xlsx_path, html_path):
        print(p.name, p.stat().st_size, 'bytes')

    comparison_df, chart_path = build_comparison_chart(df, outdir / 'Gistda_Price_List_comparison.html')
    print('Comparison chart:', chart_path, '(', len(comparison_df), 'satellites )')


if __name__ == '__main__':
    main()
