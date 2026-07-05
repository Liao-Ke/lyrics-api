#!/usr/bin/env python3
"""LRC 歌词清洗脚本：将 .lrc 文件转换为结构化 JSON"""

import json
import re
from pathlib import Path

LRC_DIR = Path("../lrc")
OUTPUT_DIR = Path("../data")
SONGS_DIR = OUTPUT_DIR / "songs"

TIMESTAMP_RE = re.compile(r'\[(\d{1,2}):(\d{2})\.(\d{2,3})\]')
BAD_TIMESTAMP_RE = re.compile(r'\[\d{2}:\d{2}\.\d{2}-\d+\]')
MULTI_TS_RE = re.compile(r'(\[\d{2}:\d{2}\.\d{2,3}\])+')

WRITER_PATTERNS = {
    'lyricist': re.compile(r'^(?:作词|词)\s*[:：]\s*(.+)$'),
    'composer': re.compile(r'^(?:作曲|曲)\s*[:：]\s*(.+)$'),
    'arranger': re.compile(r'^编曲\s*[:：]\s*(.+)$'),
}

NOISE_PATTERNS = [
    re.compile(r'^\[by:.*\]$'),
    re.compile(r'^\[ti:.*\]$'),
    re.compile(r'^\[ar:.*\]$'),
    re.compile(r'^\[al:.*\]'),
    re.compile(r'^\[ti:.*\]\[ar:.*\]\[al:.*\]$'),
    re.compile(r'www\.\S+'),
    re.compile(r'99Lrc|歌词网|LRC歌词'),
    re.compile(r'^ISRC[\s:：\-]'),
    re.compile(r'ISRC\s+[A-Z]{2}[\-\s]'),
    re.compile(r'^OP\s*[:：\-]'),
    re.compile(r'^OP\s'),
    re.compile(r'[/／]OP\s*[:：]'),
    re.compile(r'本作品经.*授权'),
    re.compile(r'本作品声明'),
    re.compile(r'未经著作权人'),
    re.compile(r'著作权权利保留'),
    re.compile(r'^发行\s*[:：]'),
    re.compile(r'^出品公司?\s*[:：]'),
    re.compile(r'^音乐制作发行\s*[:：]'),
    re.compile(r'^推广协力\s*[:：]'),
    re.compile(r'^艺人统筹\s*[:：]'),
    re.compile(r'^制作公司\s*[:：]'),
    re.compile(r'^出品\s*[:：]'),
    re.compile(r'^配唱制作人\s*[:：]'),
    re.compile(r'^录音\s*[:：]'),
    re.compile(r'^混音\s*[:：]'),
    re.compile(r'^音频编辑\s*[:：]'),
    re.compile(r'^和声\s*[:：]'),
    re.compile(r'^合唱\s*[:：]'),
    re.compile(r'^吉他\s*[:：]'),
    re.compile(r'^钢琴\s*[:：]'),
    re.compile(r'^监制\s*[:：]'),
    re.compile(r'^录音棚\s*[:：]'),
    re.compile(r'^录音师\s*[:：]'),
    re.compile(r'^录音室\s*[:：]'),
    re.compile(r'^混音师\s*[:：]'),
    re.compile(r'^混音录音室\s*[:：]'),
    re.compile(r'^制作人\s*[:：]'),
    re.compile(r'^和声编写\s*[:：]'),
    re.compile(r'^合声\s*[:：]'),
    re.compile(r'^合声编写'),
    re.compile(r'^弦乐录音师\s*[:：]'),
    re.compile(r'^弦乐录音室\s*[:：]'),
    re.compile(r'^弦乐\s*[:：]'),
    re.compile(r'^录音工程\s*[:：]'),
    re.compile(r'^混音工程\s*[:：]'),
    re.compile(r'^鼓\s*[:：]'),
    re.compile(r'^\d+(st|nd|rd|th)\s+Violin', re.IGNORECASE),
    re.compile(r'^Violas\s*[:：]'),
    re.compile(r'^Cellos\s*[:：]'),
    re.compile(r'^C\.Bass\s*[:：]'),
    re.compile(r'^弦乐助理\s*[:：]'),
]

TITLE_LINE_RE = re.compile(r'^[^\s]+\s*[-–—]\s*[^\s]+')

CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
HIRAGANA_RE = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')
LATIN_RE = re.compile(r'[a-zA-Z]{3,}')
KOREAN_RE = re.compile(r'[\uac00-\ud7af\u1100-\u11ff]')


def parse_timestamp(ts_str):
    m = TIMESTAMP_RE.match(ts_str)
    if not m:
        return None
    minutes, seconds, frac = int(m.group(1)), int(m.group(2)), m.group(3)
    if len(frac) == 2:
        frac += '0'
    return minutes * 60 + seconds + int(frac) / 1000


def format_time(seconds):
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m:02d}:{s:06.3f}"


def extract_timestamps(line):
    timestamps = []
    for m in TIMESTAMP_RE.finditer(line):
        ts = parse_timestamp(m.group(0))
        if ts is not None:
            timestamps.append((ts, m.group(0)))
    return timestamps


def get_text_after_timestamps(line):
    last_end = 0
    for m in TIMESTAMP_RE.finditer(line):
        last_end = m.end()
    text = line[last_end:].strip()
    text = BAD_TIMESTAMP_RE.sub('', text).strip()
    return text


def is_noise(text):
    for pat in NOISE_PATTERNS:
        if pat.search(text):
            return True
    return False


def is_writer_line(text):
    for field, pat in WRITER_PATTERNS.items():
        m = pat.match(text)
        if m:
            return field, m.group(1).strip()
    return None, None


def is_title_line(text, expected_artist):
    if not TITLE_LINE_RE.match(text):
        return False
    parts = re.split(r'\s*[-–—]\s*', text, maxsplit=1)
    if len(parts) != 2:
        return False
    return True


def detect_language(text):
    cjk = bool(CJK_RE.search(text))
    hiragana = bool(HIRAGANA_RE.search(text))
    latin = bool(LATIN_RE.search(text))
    korean = bool(KOREAN_RE.search(text))
    if hiragana:
        return 'ja'
    if korean:
        return 'ko'
    if cjk:
        return 'zh'
    if latin:
        return 'en'
    return 'other'


def is_translation_pair(text1, text2):
    lang1 = detect_language(text1)
    lang2 = detect_language(text2)
    if lang1 == lang2:
        return False
    if {lang1, lang2} == {'zh', 'en'}:
        return True
    if {lang1, lang2} == {'ja', 'zh'}:
        return True
    if {lang1, lang2} == {'ko', 'zh'}:
        return True
    if {lang1, lang2} == {'en', 'ja'}:
        return True
    if lang1 != lang2 and ('zh' in (lang1, lang2) or 'en' in (lang1, lang2)):
        return True
    return False


def parse_filename(filename):
    base = filename[:-4]
    parts = base.split(' - ', 1)
    if len(parts) != 2:
        return base, None, None
    title_raw, artist = parts
    version = None
    m = re.search(r'[\(（]([^)）]+)[\)）]', title_raw)
    if m:
        version = m.group(1)
    title_clean = re.sub(r'\s*[\(（][^)）]*[\)）]\s*', '', title_raw).strip()
    return title_clean, artist, version, title_raw


def normalize_key(s):
    return re.sub(r'\s+', ' ', s.strip().lower())


def parse_lrc(filepath, filename):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        raw_lines = f.readlines()

    title_info = parse_filename(filename)
    if len(title_info) == 4:
        title_clean, artist, version, title_raw = title_info
    else:
        title_clean, artist, version = filename[:-4], None, None
        title_raw = filename[:-4]

    writers = {'lyricist': None, 'composer': None, 'arranger': None}
    lyric_entries = []
    skipped_noise = 0

    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line:
            continue

        line = BAD_TIMESTAMP_RE.sub('', line)

        timestamps = extract_timestamps(line)
        if not timestamps:
            continue

        text = get_text_after_timestamps(line)
        if not text:
            continue

        if is_noise(text):
            skipped_noise += 1
            continue

        writer_field, writer_value = is_writer_line(text)
        if writer_field and writer_value:
            if not writers[writer_field]:
                writers[writer_field] = writer_value
            continue

        if artist and is_title_line(text, artist):
            parts = re.split(r'\s*[-–—]\s*', text, maxsplit=1)
            if len(parts) == 2 and normalize_key(parts[1]) == normalize_key(artist):
                continue

        for ts, ts_str in timestamps:
            lyric_entries.append({
                'time': round(ts, 3),
                'time_str': ts_str[1:-1],
                'text': text,
            })

    lyric_entries.sort(key=lambda x: x['time'])

    lyrics = []
    has_translation = False
    i = 0
    while i < len(lyric_entries):
        entry = lyric_entries[i]
        if i + 1 < len(lyric_entries):
            next_entry = lyric_entries[i + 1]
            if abs(entry['time'] - next_entry['time']) < 0.001:
                if is_translation_pair(entry['text'], next_entry['text']):
                    lang1 = detect_language(entry['text'])
                    lang2 = detect_language(next_entry['text'])
                    if lang1 in ('zh', 'ja', 'ko') and lang2 == 'en':
                        orig, trans = next_entry, entry
                    elif lang1 == 'en' and lang2 in ('zh', 'ja', 'ko'):
                        orig, trans = entry, next_entry
                    elif lang1 == 'ja' and lang2 == 'zh':
                        orig, trans = entry, next_entry
                    elif lang1 == 'zh' and lang2 == 'ja':
                        orig, trans = entry, next_entry
                    else:
                        orig, trans = entry, next_entry
                    lyrics.append({
                        'time': orig['time'],
                        'time_str': orig['time_str'],
                        'text': orig['text'],
                        'translation': trans['text'],
                    })
                    has_translation = True
                    i += 2
                    continue
        lyrics.append({
            'time': entry['time'],
            'time_str': entry['time_str'],
            'text': entry['text'],
            'translation': None,
        })
        i += 1

    group_key = None
    if title_clean and artist:
        group_key = f"{normalize_key(title_clean)}|{normalize_key(artist)}"

    return {
        'title': title_clean,
        'title_raw': title_raw,
        'version': version,
        'artist': artist,
        'group_key': group_key,
        'writers': writers,
        'lyrics': lyrics,
        'has_translation': has_translation,
        'source_file': filename,
        '_stats': {
            'total_lines': len(raw_lines),
            'lyric_count': len(lyrics),
            'noise_removed': skipped_noise,
        }
    }


def main():
    SONGS_DIR.mkdir(parents=True, exist_ok=True)

    all_songs = []
    empty_files = []

    lrc_files = sorted(f for f in LRC_DIR.iterdir() if f.suffix == '.lrc')
    print(f"Found {len(lrc_files)} LRC files")

    for lrc_file in lrc_files:
        result = parse_lrc(lrc_file, lrc_file.name)

        if result['_stats']['lyric_count'] == 0:
            empty_files.append(lrc_file.name)
            continue

        out_name = lrc_file.stem + '.json'
        out_path = SONGS_DIR / out_name
        song_data = {k: v for k, v in result.items() if k != '_stats'}
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)

        all_songs.append({
            'title': result['title'],
            'title_raw': result['title_raw'],
            'version': result['version'],
            'artist': result['artist'],
            'group_key': result['group_key'],
            'has_translation': result['has_translation'],
            'source_file': result['source_file'],
            'json_file': out_name,
            'lyric_count': result['_stats']['lyric_count'],
        })

    index = {
        'total': len(all_songs),
        'empty_files': empty_files,
        'songs': all_songs,
    }
    with open(OUTPUT_DIR / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Processed: {len(all_songs)} songs")
    print(f"Empty/skipped: {len(empty_files)} files")
    if empty_files:
        for ef in empty_files:
            print(f"  - {ef}")


if __name__ == '__main__':
    main()
