"""Clean, client-friendly SEO report PDF generator.

Design philosophy:
- One headline grade per page, color-coded
- Big numbers, generous whitespace
- Plain English labels (no jargon)
- 5 focused pages: Cover, Health, Visibility, Tracked Keywords, Work Done, Action Plan
"""
from typing import Dict, Any, List, Tuple

# ─── Color palette (RGB) ───
INK = (24, 27, 35)
INK_SOFT = (88, 96, 110)
INK_MUTED = (148, 156, 168)
HAIRLINE = (228, 230, 234)
PAPER = (252, 252, 254)
SURFACE = (246, 247, 250)

ACCENT = (17, 24, 39)         # near-black headline
GOOD = (15, 145, 100)         # calm green
WARN = (200, 126, 20)         # amber
BAD = (200, 60, 60)           # muted red
INFO = (62, 99, 180)          # blue

PAGE_W = 210
PAGE_H = 297
MARGIN_X = 16


# ─── Text safety ───
_REPL = {
    '‘': "'", '’': "'", '“': '"', '”': '"',
    '–': '-', '—': '--', '…': '...', ' ': ' ',
    '•': '*', '●': '*', '○': 'o', '✔': '[OK]',
    '✖': '[X]', '▲': 'UP', '▼': 'DOWN', '↑': 'UP',
    '↓': 'DOWN', '→': '->', '←': '<-',
}


def _safe(text, max_len: int = 500) -> str:
    if text is None:
        return ""
    s = str(text)[:max_len]
    for old, new in _REPL.items():
        s = s.replace(old, new)
    return s.encode('latin-1', errors='replace').decode('latin-1')


# ─── Grading helpers ───
def _letter(score: float) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    if score > 0:   return "F"
    return "—"


def _verdict(score: float) -> str:
    if score >= 85: return "Strong — site is healthy and competitive."
    if score >= 70: return "Good — solid foundation with room to grow."
    if score >= 55: return "Fair — meaningful gaps to close this period."
    if score >= 40: return "Needs work — several areas need attention."
    if score > 0:   return "Critical — urgent fixes required to compete."
    return "No audit data yet — run a scan to see your score."


def _grade_color(score: float) -> Tuple[int, int, int]:
    if score >= 80: return GOOD
    if score >= 60: return WARN
    if score >= 40: return (200, 100, 50)
    if score > 0:   return BAD
    return INK_MUTED


# ─── Drawing primitives ───
def _hline(pdf, y: float, color=HAIRLINE):
    pdf.set_draw_color(*color)
    pdf.set_line_width(0.2)
    pdf.line(MARGIN_X, y, PAGE_W - MARGIN_X, y)


def _eyebrow(pdf, text: str, color=INK_MUTED):
    """Small uppercase label above a section."""
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*color)
    pdf.cell(0, 4, _safe(text.upper()), ln=True)


def _h1(pdf, text: str):
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, _safe(text), ln=True)


def _h2(pdf, text: str):
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, _safe(text), ln=True)


def _body(pdf, text: str, color=INK_SOFT, size=9.5, height=5):
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, height, _safe(text, 1500))


def _kpi(pdf, x, y, w, h, label, value, sub: str = "", tone: Tuple[int,int,int] = INK):
    """Minimal KPI cell — no card frame, just typography."""
    pdf.set_xy(x, y)
    pdf.set_text_color(*INK_MUTED)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.cell(w, 4, _safe(label.upper()), ln=False)

    pdf.set_xy(x, y + 5)
    pdf.set_text_color(*tone)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(w, 10, _safe(str(value)), ln=False)

    if sub:
        pdf.set_xy(x, y + 17)
        pdf.set_text_color(*INK_SOFT)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(w, 4, _safe(sub), ln=False)


def _score_bar(pdf, x: float, y: float, w: float, h: float, label: str, score: float):
    """Horizontal score bar with label, score, and color-coded fill."""
    score = max(0, min(100, score or 0))
    color = _grade_color(score)

    # Label
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*INK)
    pdf.cell(50, h, _safe(label), ln=False)

    # Score number (right side)
    pdf.set_xy(x + 50, y)
    pdf.set_text_color(*color)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(15, h, f"{int(score)}", ln=False)

    # Bar track
    bar_x = x + 68
    bar_w = w - 80
    bar_y = y + h / 2 - 1.5
    pdf.set_fill_color(*HAIRLINE)
    pdf.rect(bar_x, bar_y, bar_w, 3, style="F")
    # Bar fill
    fill_w = bar_w * (score / 100)
    pdf.set_fill_color(*color)
    pdf.rect(bar_x, bar_y, fill_w, 3, style="F")


def _delta_pill(pdf, x: float, y: float, value: float, suffix: str = ""):
    """Compact +/- delta pill, color-coded."""
    if value == 0:
        color = INK_MUTED
        text = "no change"
    elif value > 0:
        color = GOOD
        text = f"+{value}{suffix}"
    else:
        color = BAD
        text = f"{value}{suffix}"
    pdf.set_xy(x, y)
    pdf.set_text_color(*color)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 4, _safe(text), ln=False)


# ─── Page builders ───
def _page_cover(pdf, data: Dict[str, Any]):
    """Cover: domain, big letter grade, verdict, period, what's inside."""
    pdf.add_page()
    audit = data.get("audit") or {}
    score = audit.get("health_score", 0) or 0
    grade = _letter(score)
    color = _grade_color(score)

    # Top eyebrow
    pdf.set_y(28)
    pdf.set_x(MARGIN_X)
    _eyebrow(pdf, "SEO Performance Report")

    # Domain — large, tight
    pdf.set_x(MARGIN_X)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*INK)
    pdf.cell(0, 14, _safe(data.get("domain", "")), ln=True)

    # Period
    pdf.set_x(MARGIN_X)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK_SOFT)
    period = data.get("report_month") or "Latest snapshot"
    gen = data.get("generated_at", "")[:10]
    pdf.cell(0, 6, _safe(f"Reporting period: {period}    Generated: {gen}"), ln=True)

    # ─── Big grade block ───
    pdf.set_y(96)
    pdf.set_x(MARGIN_X)
    _eyebrow(pdf, "Overall SEO Grade")

    pdf.set_xy(MARGIN_X, 102)
    pdf.set_font("Helvetica", "B", 110)
    pdf.set_text_color(*color)
    pdf.cell(70, 50, grade, ln=False)

    # Score detail right of grade
    pdf.set_xy(MARGIN_X + 75, 110)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(*INK)
    pdf.cell(40, 16, f"{int(score)}/100", ln=False)

    # Score change
    change = audit.get("score_change", 0) or 0
    pdf.set_xy(MARGIN_X + 75, 130)
    if change != 0:
        pdf.set_text_color(*(GOOD if change > 0 else BAD))
        pdf.set_font("Helvetica", "B", 11)
        arrow = "+" if change > 0 else ""
        pdf.cell(0, 6, _safe(f"{arrow}{change} vs previous period"), ln=False)
    else:
        pdf.set_text_color(*INK_MUTED)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "First period — no comparison yet", ln=False)

    # Verdict
    pdf.set_xy(MARGIN_X, 165)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*INK)
    pdf.multi_cell(PAGE_W - 2 * MARGIN_X, 7, _safe(_verdict(score)))

    # Headline KPIs strip
    pdf.set_y(190)
    _hline(pdf, 188)
    kw = data.get("keywords") or {}
    fixes = data.get("fixes", {}) or {}

    kpi_y = 195
    kpi_w = (PAGE_W - 2 * MARGIN_X) / 4
    _kpi(pdf, MARGIN_X + kpi_w * 0, kpi_y, kpi_w, 24,
         "Keywords ranking", kw.get("total", 0) or 0,
         sub=f"{kw.get('keywords_change', 0):+d} this period" if kw.get("keywords_change") else "")
    _kpi(pdf, MARGIN_X + kpi_w * 1, kpi_y, kpi_w, 24,
         "Page 1 keywords", kw.get("top10", 0) or 0,
         sub=f"of {kw.get('total', 0) or 0} total")
    _kpi(pdf, MARGIN_X + kpi_w * 2, kpi_y, kpi_w, 24,
         "Monthly clicks", kw.get("total_clicks", 0) or 0,
         sub=f"{kw.get('clicks_change', 0):+d}" if kw.get("clicks_change") else "")
    _kpi(pdf, MARGIN_X + kpi_w * 3, kpi_y, kpi_w, 24,
         "Fixes applied", fixes.get("applied_this_month", 0) or 0,
         sub=f"{fixes.get('pending', 0)} still pending")

    # What's inside
    pdf.set_y(235)
    _hline(pdf, 233)
    _eyebrow(pdf, "What's inside this report")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*INK_SOFT)
    items = [
        "Health snapshot — your site graded across 5 categories.",
        "Search visibility — what people search and where you rank.",
        "Priority keywords — progress toward your target positions.",
        "Work completed — what was fixed this period.",
        "Action plan — the highest-leverage moves for next period.",
    ]
    for it in items:
        pdf.set_x(MARGIN_X)
        pdf.cell(4, 5, "—", ln=False)
        pdf.cell(0, 5, _safe(it), ln=True)


def _page_health(pdf, data: Dict[str, Any]):
    """Page 2: Score breakdown across 5 categories + issues summary."""
    pdf.add_page()
    audit = data.get("audit") or {}

    pdf.set_y(20)
    pdf.set_x(MARGIN_X)
    _eyebrow(pdf, "01 — Health snapshot")
    _h1(pdf, "How your site scores across 5 categories")
    pdf.set_x(MARGIN_X)
    _body(pdf, "Each category contributes to your overall SEO grade. "
                "Bars fill green when strong, amber when soft, red when urgent.", size=10)
    pdf.ln(3)

    if not audit:
        _body(pdf, "No audit data yet for this period. Run a fresh audit to see scores.")
        return

    # Score bars
    cats = [
        ("Technical health", audit.get("technical_score", 0) or 0,
         "Crawl errors, broken links, missing meta tags."),
        ("Content quality", audit.get("content_score", 0) or 0,
         "Headings, depth, keyword use, readability."),
        ("Page speed", audit.get("performance_score", 0) or 0,
         "Load time, Core Web Vitals, render performance."),
        ("Mobile experience", audit.get("mobile_score", 0) or 0,
         "Responsive layout, tap targets, viewport setup."),
        ("Security", audit.get("security_score", 0) or 0,
         "HTTPS, headers, cookie flags, mixed content."),
    ]

    pdf.set_y(60)
    bar_w = PAGE_W - 2 * MARGIN_X
    for label, score, hint in cats:
        y = pdf.get_y()
        _score_bar(pdf, MARGIN_X, y, bar_w, 7, label, score)
        # Hint line
        pdf.set_xy(MARGIN_X, y + 7)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*INK_MUTED)
        pdf.cell(0, 4, _safe(hint), ln=True)
        pdf.ln(4)

    # Issues summary block
    pdf.ln(4)
    _hline(pdf, pdf.get_y())
    pdf.ln(4)
    pdf.set_x(MARGIN_X)
    _eyebrow(pdf, "Issues found this scan")
    pdf.ln(2)

    total_issues = audit.get("total_issues", 0) or 0
    critical = audit.get("critical_issues", 0) or 0
    issues_change = audit.get("issues_change", 0) or 0
    pages = audit.get("pages_crawled", 0) or 0

    # Three big numbers
    iy = pdf.get_y()
    iw = (PAGE_W - 2 * MARGIN_X) / 3
    _kpi(pdf, MARGIN_X, iy, iw, 24, "Pages scanned", pages)
    _kpi(pdf, MARGIN_X + iw, iy, iw, 24, "Total issues", total_issues,
         sub=f"{abs(issues_change)} {'fewer' if issues_change < 0 else 'more'} than last" if issues_change else "",
         tone=(GOOD if issues_change < 0 else BAD if issues_change > 0 else INK))
    _kpi(pdf, MARGIN_X + iw * 2, iy, iw, 24, "Critical", critical,
         sub="needs attention now" if critical else "none",
         tone=(BAD if critical else GOOD))


def _page_visibility(pdf, data: Dict[str, Any]):
    """Page 3: Search visibility — keywords, clicks, top movers, top traffic."""
    pdf.add_page()
    kw = data.get("keywords") or {}

    pdf.set_y(20)
    pdf.set_x(MARGIN_X)
    _eyebrow(pdf, "02 — Search visibility")
    _h1(pdf, "Where you appear in Google")
    _body(pdf, "Pulled from Google Search Console for this period. "
                "Shows what people searched, how often you appeared, and how often they clicked.", size=10)
    pdf.ln(3)

    if not kw:
        _body(pdf, "No keyword data yet. Connect Google Search Console to start tracking.")
        return

    # 4 KPIs
    kpi_y = pdf.get_y()
    kpi_w = (PAGE_W - 2 * MARGIN_X) / 4
    _kpi(pdf, MARGIN_X, kpi_y, kpi_w, 24, "Keywords", kw.get("total", 0) or 0,
         sub=f"{kw.get('keywords_change', 0):+d}" if kw.get("keywords_change") else "")
    _kpi(pdf, MARGIN_X + kpi_w, kpi_y, kpi_w, 24, "Clicks", kw.get("total_clicks", 0) or 0,
         sub=f"{kw.get('clicks_change', 0):+d}" if kw.get("clicks_change") else "")
    _kpi(pdf, MARGIN_X + kpi_w * 2, kpi_y, kpi_w, 24, "Impressions", kw.get("total_impressions", 0) or 0,
         sub=f"{kw.get('impressions_change', 0):+d}" if kw.get("impressions_change") else "")
    _kpi(pdf, MARGIN_X + kpi_w * 3, kpi_y, kpi_w, 24, "Avg position",
         f"{kw.get('avg_position', 0):.1f}" if kw.get("avg_position") else "—")

    pdf.set_y(kpi_y + 30)

    # Ranking distribution
    _hline(pdf, pdf.get_y())
    pdf.ln(3)
    _eyebrow(pdf, "Where keywords rank")
    pdf.ln(2)
    top3 = kw.get("top3", 0) or 0
    top10 = kw.get("top10", 0) or 0
    top20 = kw.get("top20", 0) or 0
    total = kw.get("total", 0) or 1
    dy = pdf.get_y()
    _score_bar(pdf, MARGIN_X, dy, PAGE_W - 2 * MARGIN_X, 6, "Top 3 (gold)", min(100, top3 / max(1, total) * 100))
    pdf.set_xy(MARGIN_X + 50, dy)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*INK)
    pdf.cell(15, 6, str(top3), ln=False)
    pdf.ln(8)

    dy = pdf.get_y()
    _score_bar(pdf, MARGIN_X, dy, PAGE_W - 2 * MARGIN_X, 6, "Top 10 (page 1)", min(100, top10 / max(1, total) * 100))
    pdf.set_xy(MARGIN_X + 50, dy)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(15, 6, str(top10), ln=False)
    pdf.ln(8)

    dy = pdf.get_y()
    _score_bar(pdf, MARGIN_X, dy, PAGE_W - 2 * MARGIN_X, 6, "Top 20 (pages 1-2)", min(100, top20 / max(1, total) * 100))
    pdf.set_xy(MARGIN_X + 50, dy)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(15, 6, str(top20), ln=False)
    pdf.ln(10)

    # Top movers
    rc = kw.get("ranking_changes", {}) or {}
    improved = rc.get("improved", []) or []
    declined = rc.get("declined", []) or []

    if improved or declined:
        _hline(pdf, pdf.get_y())
        pdf.ln(3)
        _eyebrow(pdf, "Biggest movers this period")
        pdf.ln(2)

        col_w = (PAGE_W - 2 * MARGIN_X) / 2 - 3

        # Two-column layout: wins left, watch right
        start_y = pdf.get_y()

        # Left: wins
        pdf.set_xy(MARGIN_X, start_y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*GOOD)
        pdf.cell(col_w, 6, _safe(f"Moved up   {len(improved)}"), ln=True)
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", "", 9)
        for c in improved[:6]:
            pdf.set_x(MARGIN_X)
            kw_text = _safe(c.get('query', ''), 38)
            pdf.cell(col_w - 30, 5, kw_text, ln=False)
            pdf.set_text_color(*GOOD)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(30, 5, f"#{int(c.get('previous',0))} > #{int(c.get('current',0))}", ln=True)
            pdf.set_text_color(*INK)
            pdf.set_font("Helvetica", "", 9)

        # Right: declined
        right_y = start_y
        pdf.set_xy(MARGIN_X + col_w + 6, right_y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*BAD)
        pdf.cell(col_w, 6, _safe(f"Watching   {len(declined)}"), ln=True)
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", "", 9)
        for c in declined[:6]:
            pdf.set_x(MARGIN_X + col_w + 6)
            kw_text = _safe(c.get('query', ''), 38)
            pdf.cell(col_w - 30, 5, kw_text, ln=False)
            pdf.set_text_color(*BAD)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(30, 5, f"#{int(c.get('previous',0))} > #{int(c.get('current',0))}", ln=True)
            pdf.set_text_color(*INK)
            pdf.set_font("Helvetica", "", 9)

    # Top keywords table
    pdf.ln(6)
    _hline(pdf, pdf.get_y())
    pdf.ln(3)
    _eyebrow(pdf, "Top 10 keywords driving traffic")
    pdf.ln(2)

    top_kws = kw.get("top_keywords", []) or []
    if top_kws:
        # Header
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*INK_MUTED)
        pdf.set_x(MARGIN_X)
        pdf.cell(110, 5, "KEYWORD", ln=False)
        pdf.cell(25, 5, "POSITION", ln=False, align="C")
        pdf.cell(20, 5, "CLICKS", ln=False, align="R")
        pdf.cell(0, 5, "IMPRESSIONS", ln=True, align="R")

        for i, k in enumerate(top_kws[:10]):
            y = pdf.get_y()
            if i % 2 == 0:
                pdf.set_fill_color(*SURFACE)
                pdf.rect(MARGIN_X - 1, y - 0.5, PAGE_W - 2 * MARGIN_X + 2, 6, style="F")
            pdf.set_xy(MARGIN_X, y)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*INK)
            pdf.cell(110, 6, _safe(k.get('query', ''), 60), ln=False)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(25, 6, f"#{int(k.get('position') or 0)}", ln=False, align="C")
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(20, 6, str(k.get('clicks', 0)), ln=False, align="R")
            pdf.set_text_color(*INK_SOFT)
            pdf.cell(0, 6, str(k.get('impressions', 0)), ln=True, align="R")


def _page_tracked(pdf, data: Dict[str, Any]):
    """Page 4: Priority keywords (Road to #1) — progress toward target."""
    tracked = data.get("tracked_keywords", []) or []
    if not tracked:
        return

    pdf.add_page()
    pdf.set_y(20)
    pdf.set_x(MARGIN_X)
    _eyebrow(pdf, "03 — Priority keywords")
    _h1(pdf, "Road to #1")
    _body(pdf, "Keywords selected as primary targets. "
                "Bars show progress from where we started toward the target position.", size=10)
    pdf.ln(4)

    # Header
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*INK_MUTED)
    pdf.set_x(MARGIN_X)
    pdf.cell(80, 5, "KEYWORD", ln=False)
    pdf.cell(20, 5, "CURRENT", ln=False, align="C")
    pdf.cell(20, 5, "TARGET", ln=False, align="C")
    pdf.cell(0, 5, "PROGRESS", ln=True, align="R")
    _hline(pdf, pdf.get_y() + 1)
    pdf.ln(3)

    for tk in tracked[:18]:
        kw = tk.get("keyword", "")
        pos = tk.get("position")
        target = 1
        clicks = tk.get("clicks", 0) or 0

        # Compute "progress" — how close we are to position 1
        # Assume worst-case is position 100; 100 = 0% progress, position 1 = 100%
        if pos is None or pos > 100:
            pct = 0
        else:
            pct = max(0, min(100, (101 - pos) / 100 * 100))

        y = pdf.get_y()
        pdf.set_xy(MARGIN_X, y)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(80, 7, _safe(kw, 50), ln=False)

        # Current pos
        if pos:
            pos_color = GOOD if pos <= 3 else (WARN if pos <= 10 else INK)
            pdf.set_text_color(*pos_color)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(20, 7, f"#{int(pos)}", ln=False, align="C")
        else:
            pdf.set_text_color(*INK_MUTED)
            pdf.set_font("Helvetica", "", 9.5)
            pdf.cell(20, 7, "not ranked", ln=False, align="C")

        # Target
        pdf.set_text_color(*INK_SOFT)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.cell(20, 7, f"#{target}", ln=False, align="C")

        # Progress bar (right-aligned)
        bar_x = MARGIN_X + 130
        bar_w = PAGE_W - MARGIN_X - bar_x
        pdf.set_fill_color(*HAIRLINE)
        pdf.rect(bar_x, y + 2.5, bar_w, 2.5, style="F")
        if pct > 0:
            color = GOOD if pos and pos <= 3 else (WARN if pos and pos <= 10 else INFO)
            pdf.set_fill_color(*color)
            pdf.rect(bar_x, y + 2.5, bar_w * (pct / 100), 2.5, style="F")
        pdf.ln(8)


def _page_work_done(pdf, data: Dict[str, Any]):
    """Page 5: Work completed this period."""
    pdf.add_page()
    fixes = data.get("fixes", {}) or {}
    inception = data.get("since_inception") or {}

    pdf.set_y(20)
    pdf.set_x(MARGIN_X)
    _eyebrow(pdf, "04 — Work done")
    _h1(pdf, "What we did this period")
    _body(pdf, "Specific changes pushed live to your site, broken down by type.", size=10)
    pdf.ln(3)

    # KPIs
    kpi_y = pdf.get_y()
    kpi_w = (PAGE_W - 2 * MARGIN_X) / 3
    _kpi(pdf, MARGIN_X, kpi_y, kpi_w, 24,
         "Applied this period", fixes.get("applied_this_month", 0) or 0, tone=GOOD)
    _kpi(pdf, MARGIN_X + kpi_w, kpi_y, kpi_w, 24,
         "Applied all-time", fixes.get("applied", 0) or 0)
    _kpi(pdf, MARGIN_X + kpi_w * 2, kpi_y, kpi_w, 24,
         "Pending review", fixes.get("pending", 0) or 0,
         tone=WARN if fixes.get("pending", 0) else INK_SOFT)

    pdf.set_y(kpi_y + 32)
    _hline(pdf, pdf.get_y())
    pdf.ln(3)

    # Breakdown by type — plain English
    by_type = fixes.get("by_type_this_month") or fixes.get("by_type") or {}
    type_labels = {
        "alt_text": "Alt text added to images",
        "meta_title": "Page titles rewritten",
        "meta_description": "Search snippets improved",
        "thin_content": "Thin pages expanded",
        "structured_data": "Schema/rich snippets added",
        "broken_link": "Broken links fixed",
        "internal_link": "Internal links added",
        "image_compression": "Images compressed",
        "h1_fix": "Heading structure fixed",
        "canonical": "Duplicate-content tags fixed",
    }

    if by_type:
        _eyebrow(pdf, "Breakdown by type")
        pdf.ln(2)
        for fix_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            label = type_labels.get(fix_type, fix_type.replace("_", " ").title())
            y = pdf.get_y()
            # Count in colored circle area
            pdf.set_fill_color(*SURFACE)
            pdf.rect(MARGIN_X, y, PAGE_W - 2 * MARGIN_X, 9, style="F")
            pdf.set_xy(MARGIN_X + 4, y + 1.5)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(*GOOD)
            pdf.cell(15, 6, str(count), ln=False)
            pdf.set_xy(MARGIN_X + 22, y + 1.5)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*INK)
            pdf.cell(0, 6, _safe(label), ln=True)
            pdf.ln(1.5)
    else:
        _body(pdf, "No fixes applied in this period yet.")

    # Since inception block
    if inception:
        pdf.ln(4)
        _hline(pdf, pdf.get_y())
        pdf.ln(3)
        _eyebrow(pdf, f"Since we started — {inception.get('tracking_started','')}")
        pdf.ln(2)
        kw = data.get("keywords") or {}
        lines = [
            f"Keywords:   {inception.get('initial_keywords',0)}  ->  {kw.get('total',0) or 0}    ({inception.get('keywords_growth',0):+d})",
            f"Clicks/mo:  {inception.get('initial_clicks',0)}  ->  {kw.get('total_clicks',0) or 0}    ({inception.get('clicks_growth',0):+d})",
            f"Audits run: {inception.get('total_audits',0)}    Fixes applied: {inception.get('total_fixes_applied',0)}",
        ]
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*INK)
        for L in lines:
            pdf.set_x(MARGIN_X)
            pdf.cell(0, 5.5, _safe(L), ln=True)


def _page_action_plan(pdf, data: Dict[str, Any]):
    """Page 6: Action plan — pull from strategy or AI summary."""
    strategy = data.get("strategy") or {}
    ai_summary = data.get("ai_summary", "") or ""

    actions: List[Tuple[str, str]] = []   # (priority, text)

    # Pull from weekly_focus first
    wf = strategy.get("weekly_focus") or {}
    for a in (wf.get("this_week") or [])[:5]:
        actions.append(("HIGH", str(a)))
    for a in (wf.get("quick_wins") or [])[:3]:
        actions.append(("QUICK", str(a)))

    # Tech priorities as fallback
    if not actions:
        for t in (strategy.get("technical_priorities") or [])[:5]:
            if isinstance(t, dict):
                actions.append((t.get("impact", "MED").upper()[:5], t.get("action", "")))

    # GEO recs
    geo = data.get("geo") or {}
    for r in (geo.get("top_recommendations") or [])[:3]:
        if isinstance(r, str):
            actions.append(("GEO", r))
        elif isinstance(r, dict):
            actions.append(("GEO", r.get("recommendation") or r.get("action") or ""))

    if not actions and not ai_summary:
        return

    pdf.add_page()
    pdf.set_y(20)
    pdf.set_x(MARGIN_X)
    _eyebrow(pdf, "05 — Action plan")
    _h1(pdf, "What's next")
    _body(pdf, "The highest-leverage moves for the next reporting period.", size=10)
    pdf.ln(4)

    if actions:
        for i, (prio, text) in enumerate(actions[:12], 1):
            if not text.strip():
                continue
            y = pdf.get_y()
            # Priority dot
            color = {"HIGH": BAD, "QUICK": GOOD, "GEO": INFO, "HIGH ": BAD,
                     "MED": WARN, "LOW": INK_MUTED}.get(prio, INK_SOFT)
            pdf.set_fill_color(*color)
            pdf.ellipse(MARGIN_X, y + 2, 3, 3, style="F")
            # Number
            pdf.set_xy(MARGIN_X + 6, y)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*INK_MUTED)
            pdf.cell(8, 5, f"{i:02d}", ln=False)
            # Priority label
            pdf.set_text_color(*color)
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.cell(15, 5, _safe(prio), ln=False)
            # Action text
            pdf.set_text_color(*INK)
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_xy(MARGIN_X + 30, y)
            pdf.multi_cell(PAGE_W - 2 * MARGIN_X - 30, 5, _safe(text, 400))
            pdf.ln(2)

    # Optional AI narrative beneath
    if ai_summary:
        pdf.ln(4)
        _hline(pdf, pdf.get_y())
        pdf.ln(3)
        _eyebrow(pdf, "Analyst notes")
        pdf.ln(1)
        # Take first 2 paragraphs
        paras = [p.strip() for p in ai_summary.split("\n\n") if p.strip()][:2]
        for p in paras:
            _body(pdf, p, size=9.5, height=5)
            pdf.ln(1)


def _footer(pdf, domain: str, generated: str):
    """Subtle footer on every page."""
    total = pdf.pages_count if hasattr(pdf, 'pages_count') else 0
    pdf.set_y(-14)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*INK_MUTED)
    pdf.cell(0, 5, _safe(f"{domain}    |    SEO Report    |    {generated[:10]}"), align="C")


def generate_pdf(data: Dict[str, Any]) -> bytes:
    """Build the full PDF report. Returns bytes."""
    from fpdf import FPDF

    class Report(FPDF):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._domain = data.get("domain", "")
            self._gen = data.get("generated_at", "")

        def footer(self):
            if self.page_no() == 1:
                return  # no footer on cover
            _footer(self, self._domain, self._gen)

    pdf = Report()
    pdf.set_auto_page_break(auto=True, margin=20)

    _page_cover(pdf, data)
    _page_health(pdf, data)
    _page_visibility(pdf, data)
    _page_tracked(pdf, data)
    _page_work_done(pdf, data)
    _page_action_plan(pdf, data)

    return bytes(pdf.output())
