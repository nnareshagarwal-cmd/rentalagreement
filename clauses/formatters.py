"""
clauses/formatters.py — Text, Date & Relationship Formatting Utilities
======================================================================
"""

import re
from datetime import datetime

def num_to_words(num):
    try:
        n = int(str(num).replace(',', '').strip())
    except (ValueError, TypeError):
        return str(num)

    a = ['', 'One ', 'Two ', 'Three ', 'Four ', 'Five ', 'Six ', 'Seven ', 'Eight ', 'Nine ', 'Ten ', 'Eleven ', 'Twelve ', 'Thirteen ', 'Fourteen ', 'Fifteen ', 'Sixteen ', 'Seventeen ', 'Eighteen ', 'Nineteen ']
    b = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

    if n == 0:
        return 'RUPEES ZERO ONLY'

    def _in_words(val):
        if val < 20:
            return a[val]
        if val < 100:
            return b[val // 10] + ((' ' + a[val % 10]) if val % 10 != 0 else ' ')
        if val < 1000:
            return a[val // 100] + 'Hundred ' + ((_in_words(val % 100)) if val % 100 != 0 else '')
        if val < 100000:
            return _in_words(val // 1000) + 'Thousand ' + ((_in_words(val % 1000)) if val % 1000 != 0 else '')
        if val < 10000000:
            return _in_words(val // 100000) + 'Lakh ' + ((_in_words(val % 100000)) if val % 100000 != 0 else '')
        return _in_words(val // 10000000) + 'Crore ' + ((_in_words(val % 10000000)) if val % 10000000 != 0 else '')

    return f"RUPEES {_in_words(n).strip().upper()} ONLY"

def _safe_int(val, default=1):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def combine_name_prefix_once(prefix, name):
    p = (prefix or '').strip()
    n = (name or '').strip()
    if not p:
        return n
    if not n:
        return ''
    if n.upper().startswith(p.upper()):
        return n
    return f"{p} {n}"

def format_careof(prefix, careof_code):
    p = str(prefix or '').strip().lower().replace('.', '')
    c = str(careof_code or '').strip().upper()
    
    # Male prefix -> always Son of ("S")
    if p in ('mr', 'master', 'shri'):
        return "S"
    
    # Female prefix (Mrs, Ms, Miss, Smt)
    if p in ('mrs', 'ms', 'miss', 'smt'):
        if 'HUSBAND' in c or 'WIFE' in c or c == 'W' or c == 'H':
            return "W"
        return "D"
        
    if 'W' in c or 'WIFE' in c or 'HUSBAND' in c or c == 'H':
        return "W"
    elif 'D' in c or 'DAUGHTER' in c:
        return "D"
    return "S"

def format_age(val):
    if val is None or str(val).strip() == "":
        return ""
    s = str(val).strip()
    try:
        f = float(s)
        return str(int(f))
    except (ValueError, TypeError):
        m = re.search(r'(\d+)(?:\.0*)?', s)
        if m:
            return m.group(1)
        return s

KNOWN_CITIES = [
    "HYDERABAD", "BENGALURU", "BANGALORE", "MUMBAI", "PUNE", "DELHI", "NEW DELHI",
    "GURGAON", "GURUGRAM", "NOIDA", "GREATER NOIDA", "CHENNAI", "KOLKATA",
    "AHMEDABAD", "JAIPUR", "CHANDIGARH", "LUCKNOW", "INDORE", "COIMBATORE", "KOCHI",
    "THIRUVANANTHAPURAM", "VISAKHAPATNAM", "VIJAYAWADA", "MYSORE", "MANGALORE",
    "NAGPUR", "NASHIK", "SURAT", "VADODARA", "BHOPAL", "PATNA", "RANCHI",
    "BHUBANESWAR", "GUWAHATI", "SECUNDERABAD", "FARIDABAD", "GHAZIABAD", "THANE"
]

def extract_city(address_str):
    if not address_str or not str(address_str).strip():
        return "HYDERABAD"
    
    addr_upper = str(address_str).upper()
    
    for city in KNOWN_CITIES:
        if re.search(r'\b' + re.escape(city) + r'\b', addr_upper):
            return city.title()
            
    parts = [p.strip() for p in addr_upper.split(',') if p.strip()]
    if len(parts) >= 2:
        for part in reversed(parts):
            cleaned = re.sub(r'\b\d{5,6}\b', '', part).strip()
            cleaned = re.sub(r'\b(TELANGANA|KARNATAKA|MAHARASHTRA|TAMIL NADU|WEST BENGAL|UTTAR PRADESH|HARYANA|GUJARAT|RAJASTHAN|KERALA|ANDHRA PRADESH|MADHYA PRADESH|BIHAR|ODISHA|PUNJAB)\b', '', cleaned).strip()
            tokens = [t for t in cleaned.split() if len(t) > 2 and not t.isdigit()]
            if tokens:
                return tokens[-1].title()
                
    return "HYDERABAD"

def format_ordinal_date(date_str):
    if not date_str or not str(date_str).strip():
        return ""
    s = str(date_str).strip()
    if " day of " in s.lower():
        return s

    def ordinal_suffix(day):
        if 11 <= day <= 13:
            return "th"
        return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

    dt = None
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
        "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y"
    ]
    s_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', s, flags=re.IGNORECASE)
    for fmt in formats:
        try:
            dt = datetime.strptime(s_clean, fmt)
            break
        except ValueError:
            pass

    if dt:
        day = dt.day
        suf = ordinal_suffix(day)
        month = dt.strftime("%B")
        year = dt.year
        return f"{day}{suf} day of {month} {year}"

    m = re.search(r'(\d{1,2})[\/\-\s]+([A-Za-z]+|\d{1,2})[\/\-\s]+(\d{4})', s)
    if m:
        d_val, m_val, y_val = m.groups()
        try:
            day = int(d_val)
            year = int(y_val)
            suf = ordinal_suffix(day)
            if m_val.isdigit():
                month = datetime.strptime(m_val, "%m").strftime("%B")
            else:
                month = datetime.strptime(m_val[:3], "%b").strftime("%B")
            return f"{day}{suf} day of {month} {year}"
        except Exception:
            pass

    return s

def add_runs_with_superscript_ordinals(paragraph, text, is_bold=False):
    """Adds text to python-docx paragraph, parsing 1st, 2nd, 3rd, 4th... into superscript runs."""
    if not text:
        return
    pattern = r'(\d+)(st|nd|rd|th)\b'
    last_idx = 0
    for match in re.finditer(pattern, text):
        start, end = match.span()
        if start > last_idx:
            r = paragraph.add_run(text[last_idx:start])
            if is_bold:
                r.bold = True
        
        num_str = match.group(1)
        suf_str = match.group(2)
        
        r_num = paragraph.add_run(num_str)
        if is_bold:
            r_num.bold = True
        
        r_suf = paragraph.add_run(suf_str)
        r_suf.font.superscript = True
        if is_bold:
            r_suf.bold = True
        
        last_idx = end
        
    if last_idx < len(text):
        r = paragraph.add_run(text[last_idx:])
        if is_bold:
            r.bold = True

def _make_target_regex(s):
    escaped = re.escape(s)
    prefix = r'\b' if re.match(r'^\w', s) else ''
    suffix = r'\b' if re.search(r'\w$', s) else ''
    return f"{prefix}{escaped}{suffix}"

def _add_runs_with_bold(paragraph, text, bold_strings):
    if not text:
        return
    valid_targets = sorted(list(set([s for s in bold_strings if s and str(s).strip() and len(str(s).strip()) > 1])), key=len, reverse=True)
    if not valid_targets:
        add_runs_with_superscript_ordinals(paragraph, text, is_bold=False)
        return
    
    patterns = [_make_target_regex(s) for s in valid_targets]
    combined_pattern = "(" + "|".join(patterns) + ")"
    parts = re.split(combined_pattern, text)
    target_set = set(valid_targets)
    
    for part in parts:
        if not part:
            continue
        is_b = part in target_set
        add_runs_with_superscript_ordinals(paragraph, part, is_bold=is_b)

def _html_bold_targets(text, bold_strings):
    if not text:
        return ""
    valid_targets = sorted(list(set([s for s in bold_strings if s and str(s).strip() and len(str(s).strip()) > 1])), key=len, reverse=True)
    for s in valid_targets:
        rgx = _make_target_regex(s)
        text = re.sub(rgx, lambda m: f"<b>{m.group(0)}</b>" if "<b>" not in text[max(0, m.start()-7):m.start()] else m.group(0), text)
    text = re.sub(r'(\d+)(st|nd|rd|th)\b', r'\1<sup>\2</sup>', text)
    return text

def clean_text(s):
    if not s or not isinstance(s, str):
        return str(s or "").strip()
    s = re.sub(r'%{2,}', '%', s)
    s = re.sub(r'\.{2,}', '.', s)
    s = re.sub(r',\s*\.', '.', s)
    s = re.sub(r'\.\s*,', '.', s)
    s = re.sub(r',+', ',', s)
    s = re.sub(r' {2,}', ' ', s)
    s = re.sub(r'\bmonth\b', 'Month', s)
    s = re.sub(r'\bmonths\b', 'Months', s)
    return s.strip()

def _is_leave_license(agreement_type):
    return "leave" in str(agreement_type).lower()

def _should_skip_clause(clause, agreement_type):
    if not _is_leave_license(agreement_type):
        try:
            num = int(clause["id"].split("_")[1])
            return num < 25 or num > 62
        except (IndexError, ValueError):
            return False
    else:
        return clause["id"] in ("description_of_the_said_premises", "licensor", "licensees")

def format_rent_increase(val, rent_increase_type=""):
    if not val or not str(val).strip():
        return ""
    s = str(val).strip()
    inc_type = str(rent_increase_type or "").strip()
    
    if inc_type == "Fixed Increase":
        return s.rstrip("%").strip()
    else:
        s_clean = s.rstrip("%").strip()
        if s_clean:
            return f"{s_clean}%"
        return ""
