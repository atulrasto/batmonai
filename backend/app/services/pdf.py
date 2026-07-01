"""PDF report generation using reportlab."""
import io
from datetime import date, datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

_STYLES = getSampleStyleSheet()
_TITLE  = ParagraphStyle("title",  parent=_STYLES["Heading1"], fontSize=16, spaceAfter=4)
_H2     = ParagraphStyle("h2",     parent=_STYLES["Heading2"], fontSize=12, spaceAfter=4)
_SMALL  = ParagraphStyle("small",  parent=_STYLES["Normal"],   fontSize=9,  textColor=colors.grey)
_NORMAL = _STYLES["Normal"]

_TABLE_STYLE = TableStyle([
    ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1a1f27")),
    ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
    ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",    (0, 0), (-1, -1), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
    ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d7de")),
    ("ALIGN",       (1, 1), (-1, -1), "RIGHT"),
    ("PADDING",     (0, 0), (-1, -1), 4),
])


def _fmt(v: float | None, dp: int = 3, unit: str = "") -> str:
    if v is None:
        return "—"
    return f"{v:.{dp}f}{(' ' + unit) if unit else ''}"


def _header(elements: list, title: str, subtitle: str, report_date: date) -> None:
    elements.append(Paragraph("⚡ batmonai", _TITLE))
    elements.append(Paragraph(title, _H2))
    elements.append(Paragraph(subtitle, _SMALL))
    elements.append(Paragraph(
        f"Report date: {report_date.isoformat()}  ·  Generated: "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        _SMALL,
    ))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d0d7de"), spaceAfter=8))


def battery_pdf(
    *,
    report_date: date,
    battery_uid: str,
    appliance_uid: str,
    site_name: str,
    nominal_v: float,
    shunt_rating_a: int,
    hourly_rows: list[dict],   # dicts with keys: bucket, avg_v, min_v, max_v, avg_i, min_i, max_i, energy_delta_wh
    events: list[dict],        # dicts with keys: kind, severity, started_at, resolved_at
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    els = []

    _header(els, "Battery Daily Report",
            f"{battery_uid}  ·  {appliance_uid}  ·  {site_name}",
            report_date)

    # Meta
    els.append(Paragraph(
        f"Nominal voltage: {nominal_v} V  ·  Shunt rating: {shunt_rating_a} A", _SMALL
    ))
    els.append(Spacer(1, 0.4*cm))

    # Summary from hourly rows
    if hourly_rows:
        all_avg_v  = [r["avg_v"]  for r in hourly_rows if r["avg_v"]  is not None]
        all_min_v  = [r["min_v"]  for r in hourly_rows if r["min_v"]  is not None]
        all_max_v  = [r["max_v"]  for r in hourly_rows if r["max_v"]  is not None]
        all_avg_i  = [r["avg_i"]  for r in hourly_rows if r["avg_i"]  is not None]
        all_energy = [r["energy_delta_wh"] for r in hourly_rows if r["energy_delta_wh"] is not None]

        summary_data = [
            ["Metric", "Value"],
            ["Average voltage",  _fmt(sum(all_avg_v)/len(all_avg_v) if all_avg_v else None, 3, "V")],
            ["Minimum voltage",  _fmt(min(all_min_v) if all_min_v else None, 3, "V")],
            ["Maximum voltage",  _fmt(max(all_max_v) if all_max_v else None, 3, "V")],
            ["Average current",  _fmt(sum(all_avg_i)/len(all_avg_i) if all_avg_i else None, 2, "A")],
            ["Total energy delta", _fmt(sum(all_energy) if all_energy else None, 1, "Wh")],
            ["Readings (hourly buckets)", str(len(hourly_rows))],
        ]
        els.append(Paragraph("Daily Summary", _H2))
        t = Table(summary_data, colWidths=[9*cm, 6*cm])
        t.setStyle(_TABLE_STYLE)
        els.append(t)
        els.append(Spacer(1, 0.5*cm))

        # Hourly breakdown
        els.append(Paragraph("Hourly Breakdown", _H2))
        table_data = [["Hour (UTC)", "Avg V", "Min V", "Max V", "Avg I", "Min I", "Max I", "Energy Wh"]]
        for r in hourly_rows:
            hour_str = r["bucket"].strftime("%H:00") if hasattr(r["bucket"], "strftime") else str(r["bucket"])[:13]
            table_data.append([
                hour_str,
                _fmt(r["avg_v"], 3),
                _fmt(r["min_v"], 3),
                _fmt(r["max_v"], 3),
                _fmt(r["avg_i"], 2),
                _fmt(r["min_i"], 2),
                _fmt(r["max_i"], 2),
                _fmt(r["energy_delta_wh"], 1),
            ])
        col_w = [2.2*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2.5*cm]
        t2 = Table(table_data, colWidths=col_w, repeatRows=1)
        t2.setStyle(_TABLE_STYLE)
        els.append(t2)
    else:
        els.append(Paragraph("No readings available for this date.", _NORMAL))

    # Events
    els.append(Spacer(1, 0.5*cm))
    els.append(Paragraph("Events", _H2))
    if events:
        ev_data = [["Kind", "Severity", "Started", "Resolved"]]
        for ev in events:
            ev_data.append([
                ev["kind"],
                ev["severity"],
                str(ev["started_at"])[:16].replace("T", " "),
                str(ev["resolved_at"])[:16].replace("T", " ") if ev["resolved_at"] else "open",
            ])
        te = Table(ev_data, colWidths=[4.5*cm, 2.5*cm, 5*cm, 5*cm])
        te.setStyle(_TABLE_STYLE)
        els.append(te)
    else:
        els.append(Paragraph("No events recorded for this date.", _NORMAL))

    doc.build(els)
    return buf.getvalue()


def ac_channel_pdf(
    *,
    report_date: date,
    channel_uid: str,
    appliance_uid: str,
    site_name: str,
    role: str,
    hourly_rows: list[dict],   # avg_v, avg_i, avg_power, avg_freq, avg_pf, energy_delta_wh
    events: list[dict],
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    els = []

    _header(els, "AC Channel Daily Report",
            f"{channel_uid}  ·  {appliance_uid}  ·  {site_name}",
            report_date)

    els.append(Paragraph(f"Role: {role}", _SMALL))
    els.append(Spacer(1, 0.4*cm))

    if hourly_rows:
        all_avg_v = [r["avg_v"] for r in hourly_rows if r["avg_v"] is not None]
        all_power = [r["avg_power"] for r in hourly_rows if r["avg_power"] is not None]
        all_energy = [r["energy_delta_wh"] for r in hourly_rows if r["energy_delta_wh"] is not None]

        summary_data = [
            ["Metric", "Value"],
            ["Average voltage",    _fmt(sum(all_avg_v)/len(all_avg_v) if all_avg_v else None, 1, "V")],
            ["Average power",      _fmt(sum(all_power)/len(all_power) if all_power else None, 1, "W")],
            ["Total energy delta", _fmt(sum(all_energy) if all_energy else None, 1, "Wh")],
            ["Hourly buckets",     str(len(hourly_rows))],
        ]
        els.append(Paragraph("Daily Summary", _H2))
        t = Table(summary_data, colWidths=[9*cm, 6*cm])
        t.setStyle(_TABLE_STYLE)
        els.append(t)
        els.append(Spacer(1, 0.5*cm))

        els.append(Paragraph("Hourly Breakdown", _H2))
        table_data = [["Hour (UTC)", "Avg V", "Avg I", "Avg Power", "Energy Wh", "Freq", "PF"]]
        for r in hourly_rows:
            hour_str = r["bucket"].strftime("%H:00") if hasattr(r["bucket"], "strftime") else str(r["bucket"])[:13]
            table_data.append([
                hour_str,
                _fmt(r["avg_v"], 1),
                _fmt(r["avg_i"], 2),
                _fmt(r["avg_power"], 1),
                _fmt(r["energy_delta_wh"], 1),
                _fmt(r["avg_freq"], 1),
                _fmt(r["avg_pf"], 2),
            ])
        col_w = [2.5*cm, 2.3*cm, 2.3*cm, 2.8*cm, 2.8*cm, 2*cm, 1.8*cm]
        t2 = Table(table_data, colWidths=col_w, repeatRows=1)
        t2.setStyle(_TABLE_STYLE)
        els.append(t2)
    else:
        els.append(Paragraph("No readings available for this date.", _NORMAL))

    els.append(Spacer(1, 0.5*cm))
    els.append(Paragraph("Events", _H2))
    if events:
        ev_data = [["Kind", "Severity", "Started", "Resolved"]]
        for ev in events:
            ev_data.append([
                ev["kind"],
                ev["severity"],
                str(ev["started_at"])[:16].replace("T", " "),
                str(ev["resolved_at"])[:16].replace("T", " ") if ev["resolved_at"] else "open",
            ])
        te = Table(ev_data, colWidths=[4.5*cm, 2.5*cm, 5*cm, 5*cm])
        te.setStyle(_TABLE_STYLE)
        els.append(te)
    else:
        els.append(Paragraph("No events recorded for this date.", _NORMAL))

    doc.build(els)
    return buf.getvalue()
