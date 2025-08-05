import json
import pdfplumber
import requests
from bs4 import BeautifulSoup
from config import settings
from db import SessionLocal, Program
from pathlib import Path


def extract_text_from_pdf(pdf_path: Path) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or '')
    return '\n'.join(text_parts)


def extract_program_data(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find('script', id='__NEXT_DATA__')
    if not script or not script.string:
        raise RuntimeError('__NEXT_DATA__ script not found')
    return json.loads(script.string)


def build_study_plan_url(program_id: int) -> str:
    return (
        f"https://api.itmo.su/constructor-ep/api/v1/static/programs/"
        f"{program_id}/plan/abit/pdf"
    )


def download_study_plan(program_id: int, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    url = build_study_plan_url(program_id)
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/pdf'}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    cd = resp.headers.get('Content-Disposition', '')
    if 'filename=' in cd:
        fname = cd.split('filename=')[1].strip('"\'')
    else:
        fname = f'{program_id}_study_plan.pdf'
    filepath = dest / fname
    filepath.write_bytes(resp.content)
    return filepath


def parse_program(slug: str, dest: Path) -> dict:
    url = f"https://abit.itmo.ru/program/master/{slug}"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
    resp.raise_for_status()
    data = extract_program_data(resp.text)
    props = data['props']['pageProps']
    api = props['apiProgram']
    pid = api['id']
    pdf_path = download_study_plan(pid, dest)
    full_text = extract_text_from_pdf(pdf_path)
    return {
        'slug': slug,
        'id': pid,
        'title': api.get('title', ''),
        'exam_dates': props.get('examDates', []),
        'admission_quotas': props.get('admission_quotas', {}),
        'study_plan_url': build_study_plan_url(pid),
        'study_plan_file': str(pdf_path),
        'study_plan_text': full_text
    }


def main():
    dest_dir = Path(__file__).parent / 'programs'
    db = SessionLocal()

    for slug in settings.PROGRAM_SLUGS:
        try:
            info = parse_program(slug, dest_dir)
            prog = Program(**info)
            db.merge(prog)
            db.commit()
            print(f"Processed: {info['title']} ({slug})")
        except Exception as e:
            db.rollback()
            print(f"Error {slug}: {e}")
    db.close()


if __name__ == '__main__':
    main()
