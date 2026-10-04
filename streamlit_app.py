"""Live demo front end for Streamlit Community Cloud (free hosting).

It calls the same pipeline as the FastAPI service: redaction, rule-based signals,
retrieval, drafting and guardrail checks all live in app/. Only the screen is different.
Run locally with:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import html
import json
import os
import time

import streamlit as st

# Streamlit Cloud keeps the key in its Secrets settings. Copy it into the environment
# before the app's settings are loaded. Locally, .env is used instead.
try:
    for key in ("GEMINI_API_KEY", "GEMINI_MODEL", "LLM_PROVIDER", "RETRIEVER"):
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
except Exception:  # no secrets file locally
    pass

from app.config import ROOT, load_settings  # noqa: E402
from app.guardrails import check_draft  # noqa: E402
from app.pipeline import Pipeline, ProviderError  # noqa: E402
from app.schemas import TicketIn  # noqa: E402

st.set_page_config(page_title="IT Ticket Reply Drafter", page_icon="🎫", layout="wide")

CAT = {"password_login": "Password and sign-in", "access_request": "Access request", "email": "Email",
       "network_vpn": "Network and VPN", "hardware": "Hardware", "software": "Software",
       "security": "Security", "other": "Other"}
REASON = {"possible_security_incident": "Possible security incident",
          "possible_outage": "Possible outage affecting several people",
          "possible_data_loss": "Possible data loss",
          "credentials_shared_in_ticket": "The customer shared a password in the ticket"}
SERIOUS = ("asks_for_a_secret", "makes_a_promise", "contains_personal_data")
PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "8"))


def human(flag: str) -> str:
    if flag.startswith("contains_personal_data"):
        kind = flag.split(":", 1)[1].lower().replace(",", ", ") if ":" in flag else "personal data"
        return f"Contains personal data ({kind}). Remove it before sending."
    if flag.startswith("cites_unknown_article"):
        return "Mentions an article that does not exist: " + flag.split(":", 1)[1]
    return {"asks_for_a_secret": "Asks the customer for a password or code. Rewrite before sending.",
            "makes_a_promise": "Promises a timeline, refund or outcome. Remove the promise before sending.",
            "no_article_cited": "Not based on a help article. Check the steps are correct."}.get(flag, flag)


@st.cache_resource
def get_pipeline() -> Pipeline:
    return Pipeline(load_settings())


@st.cache_data
def get_samples() -> list[dict]:
    return json.loads((ROOT / "data" / "samples.json").read_text(encoding="utf-8"))


def allowed() -> bool:
    """Per-visitor limit so a public demo stays inside the free Gemini quota."""
    now = time.time()
    hits = [t for t in st.session_state.get("hits", []) if now - t < 60]
    if len(hits) >= PER_MINUTE:
        st.session_state.hits = hits
        return False
    st.session_state.hits = hits + [now]
    return True


pipe = get_pipeline()

PRIO_COLOR = {"P1": "#B42318", "P2": "#C2410C", "P3": "#1F5FBF", "P4": "#5B6B7D"}

st.markdown("""
<style>
.block-container{max-width:1320px;padding-top:1.4rem;padding-bottom:2rem}
.stAppDeployButton{display:none}
.hdr{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;
     padding:4px 0 18px;margin-bottom:6px;border-bottom:1px solid #D9DEE6}
.hdr h1{font-size:1.55rem;font-weight:600;margin:0;padding:0;letter-spacing:-.01em}
.hdr p{margin:2px 0 0;color:#4D5A6A;font-size:.95rem}
.pill{font-family:'IBM Plex Mono',monospace;font-size:.78rem;color:#4D5A6A;border:1px solid #D9DEE6;
      background:#fff;border-radius:6px;padding:4px 10px;white-space:nowrap}
.pill b{color:#17202B;font-weight:500}
.lbl{font-size:.8rem;color:#7B8796;margin-bottom:2px}
.cat{font-size:1.05rem;font-weight:600}
.prio{display:inline-block;font-family:'IBM Plex Mono',monospace;font-weight:500;color:#fff;border-radius:5px;padding:1px 9px}
.sum{color:#4D5A6A;font-size:.95rem;padding-top:16px}
.esc{border-left:3px solid #B42318;background:#FBEDEC;padding:10px 14px;border-radius:0 6px 6px 0;margin:4px 0 6px;font-size:.93rem}
.esc b{color:#B42318}
.saw{font-family:'IBM Plex Mono',monospace;font-size:.78rem;line-height:1.55;background:#EEF1F5;border-radius:6px;padding:10px;
     word-break:break-word;max-height:190px;overflow:auto;margin:0 0 8px}
.chip{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:.72rem;border:1px solid #D9DEE6;
      border-radius:5px;padding:1px 7px;color:#4D5A6A;margin:0 6px 6px 0}
.art{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:.88rem;padding:7px 0;border-top:1px solid #E6E9EE}
.art:first-child{border-top:0}
.art code{font-size:.75rem;color:#7B8796;background:none;padding:0}
.bar{grid-column:2;height:4px;background:#EEF1F5;border-radius:2px;overflow:hidden}
.bar i{display:block;height:100%;background:#1F5FBF}
.side h4{font-size:.85rem;font-weight:600;color:#4D5A6A;margin:4px 0 8px}
.meta{font-family:'IBM Plex Mono',monospace;font-size:.72rem;color:#7B8796;line-height:1.8}
.empty{padding:28px 8px;color:#4D5A6A}
.empty h3{color:#17202B;font-size:1.15rem;margin:0 0 6px}
</style>
""", unsafe_allow_html=True)

status = ("<b>Offline mode</b> · rules and templates, no AI" if pipe.drafter.name == "offline"
          else f"<b>{html.escape(pipe.model)}</b> · {pipe.retriever.name} retrieval · {len(pipe.articles)} help articles")
st.markdown(f"""<div class="hdr"><div><h1>IT Ticket Reply Drafter</h1>
<p>Draft replies from your knowledge base. A person reviews and sends every one.</p></div>
<span class="pill">{status}</span></div>""", unsafe_allow_html=True)

left, right = st.columns([2, 3], gap="medium")

with left:
    with st.container(border=True):
        st.markdown("**Ticket**")
        samples = get_samples()
        pick = st.pills("Try an example", [s["label"] for s in samples], selection_mode="single", key="pick")
        chosen = next((s for s in samples if s["label"] == pick), {})
        k = pick or "own"
        with st.form("ticket", border=False):
            name = st.text_input("Customer name (optional)", value=chosen.get("customer_name") or "", max_chars=80, key=f"n_{k}")
            subject = st.text_input("Subject", value=chosen.get("subject", ""), max_chars=200, key=f"s_{k}")
            body = st.text_area("Message", value=chosen.get("body", ""), height=190, max_chars=4000, key=f"b_{k}")
            go = st.form_submit_button("Draft replies", type="primary", use_container_width=True)
        st.caption("Emails, phone numbers, card numbers, IP addresses and passwords are removed before anything "
                   "reaches the model.")

if go:
    if not subject.strip() or len(body.strip()) < 5:
        st.session_state.error = "Add a subject and a message of at least a few words."
    elif not allowed():
        st.session_state.error = ("Too many requests. This demo allows a few drafts per minute to stay on "
                                  "the free tier. Try again in a minute.")
    else:
        try:
            with st.spinner("Drafting replies…"):
                res = pipe.run(TicketIn(subject=subject.strip(), body=body.strip(),
                                        customer_name=name.strip() or None))
            st.session_state.result = res
            st.session_state.drafts = {d.tone.value: d.model_dump() for d in res.drafts}
            for t in ("concise", "detailed", "escalation"):
                st.session_state.pop(f"body_{t}", None)  # show the new drafts, not the old edits
            st.session_state.error = None
        except ProviderError as e:
            print(f"[drafter] {e}", flush=True)
            st.session_state.error = "The AI model is unavailable right now. Try again shortly."

with right:
    with st.container(border=True):
        if st.session_state.get("error"):
            st.error(st.session_state.error)
        res = st.session_state.get("result")
        if not res:
            st.markdown("""<div class="empty"><h3>Drafts appear here</h3>
Pick an example or paste a ticket. You will get:<ol style="margin:.4rem 0 0">
<li>A category, a priority and an escalation check</li>
<li>Three reply drafts based on the help articles</li>
<li>A warning on any draft that breaks a safety rule</li></ol></div>""", unsafe_allow_html=True)
        else:
            a = res.analysis
            c1, c2, c3 = st.columns([2.2, 1, 4])
            c1.markdown(f'<div class="lbl">Category</div><div class="cat">{CAT.get(a.category.value, a.category.value)}</div>',
                        unsafe_allow_html=True)
            c2.markdown(f'<div class="lbl">Priority</div><span class="prio" style="background:{PRIO_COLOR[a.priority.value]}">'
                        f'{a.priority.value}</span>', unsafe_allow_html=True)
            c3.markdown(f'<div class="sum">{html.escape(a.summary)}</div>', unsafe_allow_html=True)
            if a.needs_escalation:
                reasons = list(dict.fromkeys(REASON.get(r, r).rstrip(".") for r in a.escalation_reasons))
                st.markdown(f'<div class="esc"><b>Escalate before replying.</b> {html.escape("; ".join(reasons))}</div>',
                            unsafe_allow_html=True)

            dcol, scol = st.columns([3, 2], gap="medium")
            with dcol:
                labels = [("⚠ " if st.session_state.drafts[d.tone.value]["blocked"] else "") + d.tone.value.capitalize()
                          for d in res.drafts]
                for tab, d in zip(st.tabs(labels), res.drafts):
                    tone = d.tone.value
                    state = st.session_state.drafts[tone]
                    with tab:
                        st.caption(f"Subject: **{state['subject']}**")
                        edited = st.text_area("Reply draft", value=state["body"], height=300, key=f"body_{tone}",
                                              label_visibility="collapsed")
                        state["body"] = edited
                        for f in state["flags"]:
                            (st.error if f.startswith(SERIOUS) else st.info)(human(f))
                        if state["blocked"]:
                            if st.button("Check my edits", key=f"check_{tone}", type="primary"):
                                flags, blocked = check_draft(edited, state["kb_ids"], pipe.known_ids)
                                if tone == "escalation":
                                    flags = [x for x in flags if x != "no_article_cited"]
                                state["flags"], state["blocked"] = flags, blocked
                                st.rerun()
                        else:
                            b1, b2 = st.columns([1, 1])
                            b1.badge("Passed safety checks", icon=":material/verified:", color="green")
                            if state["kb_ids"]:
                                b2.caption("Based on " + ", ".join(state["kb_ids"]))
                            with st.expander("Copy this reply"):
                                st.code(edited, language=None, wrap_lines=True)
            with scol:
                removed = "".join(f'<span class="chip">{r.type} ×{r.count} removed</span>' for r in res.redactions) \
                    or '<span class="chip">No personal data found</span>'
                # Blank lines would end the HTML block in Markdown, so use <br> for line breaks.
                saw = "<br>".join(html.escape(line) for line in res.redacted_ticket.splitlines())
                if res.kb_sources:
                    top = max(x.score for x in res.kb_sources)
                    arts = "".join(f'<div class="art"><code>{k.id}</code><span>{html.escape(k.title)}</span>'
                                   f'<div class="bar"><i style="width:{round(k.score / top * 100)}%"></i></div></div>'
                                   for k in res.kb_sources)
                else:
                    arts = "No matching article. Drafts ask a clarifying question instead."
                st.markdown(f"""<div class="side">
<h4>What the model saw</h4><div class="saw">{saw}</div>{removed}
<h4 style="margin-top:14px">Help articles used</h4><div>{arts}</div>
<h4 style="margin-top:14px">Run details</h4>
<div class="meta">provider: {res.provider}<br>model: {html.escape(res.model)}<br>time: {res.latency_ms} ms<br>request: {res.request_id}</div>
</div>""", unsafe_allow_html=True)

st.caption("Use made-up tickets only. Nothing is sent from this page: copy a reply into your ticketing tool when you are happy with it.")
