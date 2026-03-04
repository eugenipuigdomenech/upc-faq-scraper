import html
from typing import Dict, List
from bs4 import BeautifulSoup
import re
import unicodedata


def _normalize_text(value: str) -> str:
    txt = (value or "").strip().lower()
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return txt


def _get_row_value_case_insensitive(row: Dict[str, str], wanted_key: str) -> str:
    wanted = _normalize_text(wanted_key)
    for k, v in row.items():
        if _normalize_text(k) == wanted:
            return v or ""
    return ""


def filter_approved(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    approved_values = {
        "aprovat",
        "aprovada",
        "aprovat/da",
        "aprobat",
        "approved",
        "ok",
        "si",
        "yes",
        "true",
        "1",
    }
    out = []
    for r in rows:
        estat = _normalize_text(_get_row_value_case_insensitive(r, "estat"))
        if estat in approved_values:
            out.append(r)
    return out


def _looks_like_html(text: str) -> bool:
    t = (text or "").strip()
    return "<" in t and ">" in t


def _answer_to_html_paragraph(answer: str) -> str:
    a = (answer or "").strip()
    if _looks_like_html(a):
        return a

    a = html.escape(a)
    a = a.replace("\r\n", "\n").replace("\r", "\n")
    a = a.replace("\n\n", "<br /><br />")
    a = a.replace("\n", "<br />")
    return a


def render_upc_faqaccordion(items: List[Dict[str, str]]) -> str:
    def _grouped_by_topic(rows: List[Dict[str, str]]) -> List[tuple[str, List[Dict[str, str]]]]:
        order: List[str] = []
        grouped: Dict[str, List[Dict[str, str]]] = {}
        for row in rows:
            topic = (row.get("Tema") or "").strip() or "Preguntes freqüents"
            if topic not in grouped:
                grouped[topic] = []
                order.append(topic)
            grouped[topic].append(row)
        return [(t, grouped[t]) for t in order]

    def _slug(text: str) -> str:
        base = re.sub(r"\s+", "-", (text or "").strip().lower())
        base = re.sub(r"[^a-z0-9-]", "", base)
        base = re.sub(r"-{2,}", "-", base).strip("-")
        return base or "topic"

    out: List[str] = []
    out.append('<div id="faqTopicAccordion" style="margin-bottom: 40px;">')

    topic_blocks = _grouped_by_topic(items)
    for topic_idx, (topic, topic_items) in enumerate(topic_blocks, start=1):
        topic_id = f"topic-{topic_idx}-{_slug(topic)}"
        inner_acc_id = f"faqAccordion-{topic_idx}"

        out.append(f"<!-- TOPIC {topic_idx}: {html.escape(topic)} -->")
        out.append('<div style="border: 0; box-shadow: none; border-bottom: 1px solid #D1D1D1; background: transparent;">')
        out.append(
            '<h2 style="padding: 0; margin: 0;">'
            f'<button type="button" data-bs-toggle="collapse" data-bs-target="#{topic_id}" aria-expanded="false" aria-controls="{topic_id}" '
            'style="width: 100%; text-align: left; font-size: 24px; background: #F2F8FB; padding: 24px 40px 24px 18px; '
            'font-weight: 800; color: #003E53; letter-spacing: .2px; position: relative; border: 0; border-top: 1px solid #D1D1D1; '
            'border-left: 5px solid #00769D; '
            'box-shadow: none; cursor: pointer;">'
            f"{html.escape(topic)} "
            '<span aria-hidden="true" style="position: absolute; right: 18px; top: 50%; transform: translateY(-50%); '
            'font-size: 24px; line-height: 1; color: #003E53; transition: all .25s ease;">&#8964;</span> '
            "</button></h2>"
        )
        out.append(
            f'<div id="{topic_id}" class="collapse" data-bs-parent="#faqTopicAccordion" '
            'style="border-bottom: 1px solid #D1D1D1; margin-bottom: -1px; position: relative; z-index: 1; height: 0px; overflow: hidden; '
            'transition: height 350ms ease;">'
        )
        out.append('<div style="border-top: 0; padding: 0 0 12px;">')
        out.append(f'<div id="{inner_acc_id}" data-upc-faq-accordion="1">')

        for item_idx, it in enumerate(topic_items, start=1):
            q = (it.get("Pregunta") or "").strip()
            a = (it.get("Resposta") or "").strip()
            q_html = q if _looks_like_html(q) else html.escape(q)
            a_html = _answer_to_html_paragraph(a)
            qid = f"c{topic_idx}-{item_idx}"

            out.append(f"<!-- ITEM {topic_idx}.{item_idx} -->")
            out.append('<div style="border: 0; box-shadow: none; border-bottom: 1px solid #D1D1D1; background: transparent;">')
            out.append(
                '<h2 style="padding: 0; margin: 0;">'
                f'<button type="button" data-bs-toggle="collapse" data-bs-target="#{qid}" aria-expanded="false" aria-controls="{qid}" '
                'style="width: 100%; text-align: left; font-size: 18px; background: transparent; padding: 30px 36px 30px 18px; '
                'font-weight: 500; color: #00769d; position: relative; border: 0; border-top: 1px solid #D1D1D1; '
                'box-shadow: none; cursor: pointer;">'
                f"{q_html} "
                '<span aria-hidden="true" style="position: absolute; right: 18px; top: 50%; transform: translateY(-50%); '
                'font-size: 22px; line-height: 1; color: #00769D; transition: all .25s ease;">&#8964;</span> '
                "</button></h2>"
            )
            out.append(
                f'<div id="{qid}" class="collapse" data-bs-parent="#{inner_acc_id}" '
                'style="border-bottom: 1px solid #D1D1D1; margin-bottom: -1px; position: relative; z-index: 1; height: 0px; overflow: hidden; '
                'transition: height 350ms ease;">'
            )
            out.append('<div style="border-top: 0; padding: 0 18px 18px;">')
            out.append(
                '<div style="margin: 0; font-size: 16px; font-weight: 300; line-height: 1.45; color: #636363;">'
                f"{a_html}</div>"
            )
            out.append("</div></div></div>")

        out.append("</div>")
        out.append("</div></div>")

    out.append("</div>")
    out.append("<p>")
    out.append("<script>")
    out.append(
        r"""(function () {
  const accordions = Array.from(document.querySelectorAll('[data-upc-faq-accordion="1"]'));
  if (!accordions.length) return;

  accordions.forEach((acc) => {
    const collapses = Array.from(acc.querySelectorAll('.collapse'));

    function btnFor(col) {
      return acc.querySelector('[data-bs-target="#' + col.id + '"]');
    }

    function setStyles(col, isOpen) {
      const btn = btnFor(col);
      if (btn) {
        btn.style.borderTopColor = isOpen ? '#00769D' : '#D1D1D1';
        btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        const icon = btn.querySelector('span[aria-hidden="true"]');
        if (icon) {
          icon.textContent = isOpen ? '\u2303' : '\u2304';
          icon.style.transform = 'translateY(-50%)';
        }
      }
      col.style.borderBottomColor = isOpen ? '#00769D' : '#D1D1D1';
    }

    function open(col) {
      if (col.dataset.anim === '1') return;

      collapses.forEach(other => { if (other !== col) close(other); });

      col.dataset.anim = '1';
      col.classList.add('showing');
      col.style.height = '0px';

      requestAnimationFrame(() => {
        const h = col.scrollHeight;
        col.style.height = h + 'px';
        setStyles(col, true);
      });

      const done = (e) => {
        if (e.propertyName !== 'height') return;
        col.classList.remove('showing');
        col.classList.add('show');
        col.style.height = 'auto';
        col.dataset.anim = '0';
        col.removeEventListener('transitionend', done);
      };
      col.addEventListener('transitionend', done);
    }

    function close(col) {
      if (col.dataset.anim === '1') return;
      if (!col.classList.contains('show') && col.style.height === '0px') return;

      col.dataset.anim = '1';
      col.classList.remove('show');

      const h = col.scrollHeight;
      col.style.height = h + 'px';

      requestAnimationFrame(() => {
        col.style.height = '0px';
        setStyles(col, false);
      });

      const done = (e) => {
        if (e.propertyName !== 'height') return;
        col.dataset.anim = '0';
        col.removeEventListener('transitionend', done);
      };
      col.addEventListener('transitionend', done);
    }

    acc.querySelectorAll('button[data-bs-target]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const sel = btn.getAttribute('data-bs-target');
        const col = sel ? document.querySelector(sel) : null;
        if (!col) return;

        const isOpen = col.classList.contains('show') || col.style.height === 'auto';
        if (isOpen) close(col);
        else open(col);
      });
    });

    collapses.forEach(col => {
      col.style.overflow = 'hidden';
      col.style.transition = 'height 350ms ease';
      col.style.height = '0px';
      col.classList.remove('show');
      setStyles(col, false);
    });
  });
})();"""
    )
    out.append("</script>")
    out.append("</p>")

    return _prettify_export_html("\n".join(out))


def _prettify_export_html(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    try:
        return BeautifulSoup(raw, "html.parser").prettify()
    except Exception:
        return raw


def export_text(output_path: str, text: str):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)


def approved_rows_to_html(approved_rows, log=None):
    def _log(m):
        if log:
            log(m)

    _log(f"Generant HTML per {len(approved_rows)} FAQs aprovades (UI)...")

    items = []
    for row in approved_rows:
        topic, question, answer, source = row
        items.append(
            {
                "Tema": topic,
                "Pregunta": question,
                "Resposta": answer,
                "Font": source,
            }
        )

    return render_upc_faqaccordion(items)
