import base64
import io
import logging
import textwrap

from odoo import http
from odoo.http import request
from odoo.addons.dojo_members_portal.controllers.main import DojoMemberPortal

_logger = logging.getLogger(__name__)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _render_qr_png(data: str) -> bytes:
    """Return raw PNG bytes for a QR code encoding *data*."""
    import qrcode  # lazy: not available at import time in all envs
    qr = qrcode.make(data)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()


def _composed_badge_pdf(member_name: str, member_number: str,
                        company_logo_b64=None) -> bytes:
    """Build a single-page badge PDF (600×420 px) with QR + name + optional logo.

    Returns raw PDF bytes.
    """
    from PIL import Image, ImageDraw, ImageFont  # lazy: Pillow checked at boot

    width, height = 600, 420
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)

    # Company logo — top-right corner, respecting alpha channel
    if company_logo_b64:
        try:
            logo_bytes = base64.b64decode(company_logo_b64)
            logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            max_logo = 120
            logo.thumbnail((max_logo, max_logo), Image.LANCZOS)
            lx = width - logo.width - 24
            ly = 24
            # Use alpha channel as paste mask to avoid black background artifacts
            r, g, b, alpha = logo.split()
            canvas.paste(logo.convert("RGB"), (lx, ly), mask=alpha)
        except Exception:
            _logger.debug("Badge PDF: could not embed company logo", exc_info=True)

    # QR code — left side
    png_bytes = _render_qr_png(member_number)
    qr_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    qr_size = 300
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    qr_x, qr_y = 40, (height - qr_size) // 2
    canvas.paste(qr_img, (qr_x, qr_y))

    # Text — right side, with word-wrap so long names don't overflow
    text_x = qr_x + qr_size + 24
    text_y = qr_y + 12
    max_text_width = width - text_x - 16  # pixels remaining

    try:
        font_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
    except Exception:
        font_bold = ImageFont.load_default()
    try:
        font_reg = ImageFont.truetype("DejaVuSans.ttf", 20)
    except Exception:
        font_reg = ImageFont.load_default()

    # Estimate chars per line from pixel width (rough: ~15 px per char at 28pt)
    chars_per_line = max(10, max_text_width // 16)
    wrapped_name = textwrap.fill(member_name or "", width=chars_per_line)
    dy = 0
    for line in wrapped_name.split("\n"):
        draw.text((text_x, text_y + dy), line, fill=(0, 0, 0), font=font_bold)
        dy += 36

    draw.text((text_x, text_y + dy + 8), f"#{member_number}", fill=(0x44, 0x44, 0x44), font=font_reg)

    out = io.BytesIO()
    canvas.save(out, format="PDF", resolution=150)
    return out.getvalue()


def _print_html_wrapper(pdf_url: str, title: str = "Print Badge") -> str:
    """Return a minimal HTML page embedding the PDF that auto-triggers print.

    The window is NOT auto-closed so the user can re-print or save manually.
    """
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <style>
    html, body {{ height: 100%; margin: 0; font-family: sans-serif; }}
    #toolbar {{
      position: fixed; top: 0; left: 0; right: 0; height: 40px;
      background: #1d1d1d; color: #fff; display: flex; align-items: center;
      gap: 12px; padding: 0 16px; z-index: 10; font-size: 14px;
    }}
    #toolbar button {{
      background: #fff; color: #1d1d1d; border: none; border-radius: 4px;
      padding: 4px 14px; cursor: pointer; font-size: 14px; font-weight: bold;
    }}
    iframe {{ border: 0; width: 100%; height: calc(100% - 40px); margin-top: 40px; }}
  </style>
</head>
<body>
  <div id="toolbar">
    <span>{title}</span>
    <button onclick="doPrint()">🖨 Print</button>
    <button onclick="window.close()">✕ Close</button>
  </div>
  <iframe id="f" src="{pdf_url}"></iframe>
  <script>
    function doPrint() {{
      var f = document.getElementById('f');
      try {{ f.contentWindow.print(); }} catch(e) {{ window.print(); }}
    }}
    // Auto-trigger print once PDF loads
    document.getElementById('f').onload = doPrint;
  </script>
</body>
</html>"""


def _require_instructor_or_admin(user) -> bool:
    return (
        user.has_group("dojo_base.group_dojo_instructor")
        or user.has_group("dojo_base.group_dojo_admin")
        or user.has_group("base.group_system")
    )


# ── QR Code serving ───────────────────────────────────────────────────────────

class DojoMarketingController(http.Controller):

    @http.route(
        "/dojo/marketing/qr/<int:card_id>",
        type="http",
        auth="public",
        csrf=False,
    )
    def marketing_card_qr(self, card_id, **kwargs):
        """Serve the pre-generated QR PNG for a marketing card."""
        card = request.env["dojo.marketing.card"].sudo().browse(card_id)
        if not card.exists() or not card.active or not card.qr_image:
            return request.not_found()
        png_bytes = base64.b64decode(card.qr_image)
        return request.make_response(
            png_bytes,
            headers=[
                ("Content-Type", "image/png"),
                ("Content-Length", len(png_bytes)),
                ("Cache-Control", "public, max-age=86400"),
            ],
        )

    # ── Member badge (portal / self-service) ─────────────────────────────────

    @http.route("/my/dojo/badge-qr", type="http", auth="user", csrf=False)
    def member_badge_qr(self, **kwargs):
        """Serve a per-member QR PNG (encoded with member_number)."""
        member = request.env["dojo.member"].sudo().search(
            [("partner_id", "=", request.env.user.partner_id.id)], limit=1
        )
        if not member or not member.member_number:
            return request.not_found()
        try:
            png_bytes = _render_qr_png(member.member_number)
        except Exception:
            _logger.exception("member_badge_qr: QR generation failed")
            return request.internal_server_error()
        return request.make_response(
            png_bytes,
            headers=[
                ("Content-Type", "image/png"),
                ("Content-Length", len(png_bytes)),
                ("Cache-Control", "private, max-age=300"),
            ],
        )

    @http.route("/my/dojo/badge/print", type="http", auth="user", csrf=False)
    def member_badge_print(self, **kwargs):
        """HTML print-wrapper for the member's own badge (portal self-service)."""
        member = request.env["dojo.member"].sudo().search(
            [("partner_id", "=", request.env.user.partner_id.id)], limit=1
        )
        if not member or not member.member_number:
            return request.not_found()
        html = _print_html_wrapper(
            pdf_url=f"/my/dojo/badge.pdf",
            title=f"Badge — {member.name}",
        )
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/my/dojo/badge.pdf", type="http", auth="user", csrf=False)
    def member_badge_pdf_portal(self, **kwargs):
        """Serve a printable badge PDF for the currently logged-in portal member."""
        member = request.env["dojo.member"].sudo().search(
            [("partner_id", "=", request.env.user.partner_id.id)], limit=1
        )
        if not member or not member.member_number:
            return request.not_found()
        try:
            logo_b64 = request.env.company.sudo().logo or None
            pdf_bytes = _composed_badge_pdf(member.name, member.member_number, logo_b64)
        except Exception:
            _logger.exception("member_badge_pdf_portal: PDF generation failed")
            return request.internal_server_error()
        filename = f"badge_{member.member_number}.pdf"
        return request.make_response(
            pdf_bytes,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Length", len(pdf_bytes)),
                ("Content-Disposition", f'inline; filename="{filename}"'),
                ("Cache-Control", "private, no-store"),
            ],
        )

    # ── Instructor / admin badge ──────────────────────────────────────────────

    @http.route(
        "/dojo/marketing/member/<int:member_id>/badge",
        type="http",
        auth="user",
        csrf=False,
    )
    def member_badge_view(self, member_id, **kwargs):
        """HTML print-wrapper for a specific member (instructor / admin only)."""
        if not _require_instructor_or_admin(request.env.user):
            return request.forbidden()
        html = _print_html_wrapper(
            pdf_url=f"/dojo/marketing/member/{member_id}/badge.pdf",
            title="Print Member Badge",
        )
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route(
        "/dojo/marketing/member/<int:member_id>/badge.pdf",
        type="http",
        auth="user",
        csrf=False,
    )
    def member_badge_pdf(self, member_id, **kwargs):
        """Serve a printable badge PDF for any member (instructor / admin only)."""
        if not _require_instructor_or_admin(request.env.user):
            return request.forbidden()
        member = request.env["dojo.member"].sudo().browse(member_id)
        if not member.exists() or not member.member_number:
            return request.not_found()
        try:
            logo_b64 = request.env.company.sudo().logo or None
            pdf_bytes = _composed_badge_pdf(member.name, member.member_number, logo_b64)
        except Exception:
            _logger.exception("member_badge_pdf: PDF generation failed for member %s", member_id)
            return request.internal_server_error()
        filename = f"badge_{member.member_number}.pdf"
        return request.make_response(
            pdf_bytes,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Length", len(pdf_bytes)),
                ("Content-Disposition", f'inline; filename="{filename}"'),
                ("Cache-Control", "private, no-store"),
            ],
        )


# ── Portal home extension ─────────────────────────────────────────────────────

class DojoMemberPortalMarketing(DojoMemberPortal):

    @http.route()
    def portal_dojo_home(self, tab="programs", saved=None, **kwargs):
        response = super().portal_dojo_home(tab=tab, saved=saved, **kwargs)
        # Only augment successful renders (not redirects or error pages)
        if not hasattr(response, "qcontext"):
            return response

        base_url = request.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", default=""
        )
        cards = request.env["dojo.marketing.card"].sudo().search(
            [("active", "=", True), ("publish_portal", "=", True)]
        )
        marketing_cards = []
        for card in cards:
            qr_url = None
            if card.card_type == "badge":
                qr_url = "/my/dojo/badge-qr"
            elif card.target_url:
                qr_url = f"{base_url}/dojo/marketing/qr/{card.id}"
            marketing_cards.append({
                "id": card.id,
                "card_type": card.card_type,
                "name": card.name,
                "subtitle": card.subtitle or "",
                "body": card.body or "",
                "qr_url": qr_url,
            })

        response.qcontext["marketing_cards"] = marketing_cards
        return response
