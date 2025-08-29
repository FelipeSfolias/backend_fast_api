from pathlib import Path
from datetime import datetime
import os, shutil, subprocess, tempfile
from jinja2 import Template  # NOVO

def _wkhtmltopdf_path() -> str | None:
    exe = shutil.which("wkhtmltopdf")
    if exe: return exe
    for c in (r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
              r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe"):
        if os.path.isfile(c): return c
    return None

def build_verify_code(enrollment_id: int) -> str:
    import hashlib, os
    return hashlib.sha1(f"{enrollment_id}-{os.urandom(4).hex()}".encode()).hexdigest()[:20]

DEFAULT_TEMPLATE = """
<html>
<head>
<meta charset="utf-8"/>
<style>
  body { font-family: Arial, sans-serif; margin:60px; }
  h1 { text-align:center; }
  .footer { margin-top: 24px; font-size: 12px; color: #555; }
  img.logo { max-height: 64px; }
</style>
</head>
<body>
  {% if cliente.logo_url %}<img class="logo" src="{{ cliente.logo_url }}"/>{% endif %}
  <h1>Certificado</h1>
  <p>Certificamos que <b>{{ aluno.nome }}</b> participou do evento
     <b>{{ evento.titulo }}</b> com carga horária de <b>{{ carga_horaria }}</b> horas.</p>
  <p>Código de verificação: <b>{{ codigo }}</b></p>
  <div class="footer">
    Emitido em {{ emitido_em }} — Verifique em {{ verify_url }}
  </div>
</body>
</html>
"""

def _render_html_with_template(template_html: str | None, context: dict) -> str:
    tpl = Template(template_html or DEFAULT_TEMPLATE)
    return tpl.render(**context)

def render_certificate_pdf(*, enrollment_id: int, event, student, client, verify_code: str) -> str:
    # mapeia nomes para placeholders exigidos no projeto
    ctx = {
        "aluno": {"nome": student.name},
        "evento": {"titulo": event.title},
        "carga_horaria": event.workload_hours or 0,
        "data": datetime.utcnow().strftime("%Y-%m-%d"),
        "codigo": verify_code,
        "cliente": {"logo_url": client.logo_url, "nome": client.name},
        "emitido_em": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "verify_url": f"/api/v1/{client.slug}/certificates/verify/{verify_code}",
    }
    html = _render_html_with_template(client.certificate_template_html, ctx)

    out = Path(f"certificates/{enrollment_id}_{verify_code}.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    wk = _wkhtmltopdf_path()
    if wk:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as tmp:
            tmp.write(html); tmp.flush(); tmp_path = tmp.name
        try:
            subprocess.run([wk, "--quiet", tmp_path, out.as_posix()], check=True)
        finally:
            try: os.unlink(tmp_path)
            except OSError: pass
    else:
        # fallback (WeasyPrint)
        from weasyprint import HTML
        HTML(string=html).write_pdf(out.as_posix())

    return f"/{out.as_posix()}"
