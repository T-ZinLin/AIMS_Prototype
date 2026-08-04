from __future__ import annotations

import hashlib
import html

import streamlit as st

from aims.documents import DocumentPreviewError, page_count, render_preview
from aims.fixtures import DEMO_SUBMISSIONS, INSTRUCTION, MODEL_STEPS, QUESTION, QUESTION_DISPLAY, RUBRIC
from aims.grading import grade_submission
from aims.review import divergence_summary, present_steps


# The queue mirrors the teammate prototype's lecturer view while keeping this
# MVP on one Streamlit runtime. Each seeded student opens one of the verified
# offline fixtures, so the demonstration never depends on OCR or an API.
STUDENT_QUEUE = (
    ("S026", "Jing Wen", 3, "Sign error â€” recommended demo", "Check"),
    ("S027", "Amir", 4, "Sign error â€” recommended demo", "Check"),
    ("S028", "Tessa", 0, "Blank manual entry", "Check"),
    ("S001", "Aisyah", 4, "Completely correct", "7/7"),
    ("S002", "Wei Ming", 4, "Completely correct", "7/7"),
    ("S003", "Priya", 4, "Completely correct", "7/7"),
    ("S004", "Daniel", 4, "Completely correct", "7/7"),
    ("S005", "Nur", 4, "Completely correct", "7/7"),
    ("S006", "Jun Hao", 4, "Completely correct", "7/7"),
    ("S007", "Kavya", 3, "Sign error â€” recommended demo", "5/7"),
    ("S008", "Marcus", 4, "Sign error â€” recommended demo", "5/7"),
    ("S009", "Siti", 3, "Sign error â€” recommended demo", "4/7"),
    ("S010", "Zhi Xuan", 2, "Sign error â€” recommended demo", "4/7"),
    ("S011", "Rahul", 3, "Sign error â€” recommended demo", "5/7"),
    ("S012", "Hui Ling", 3, "Sign error â€” recommended demo", "5/7"),
    ("S013", "Aaron", 3, "Sign error â€” recommended demo", "5/7"),
    ("S014", "Farah", 3, "Sign error â€” recommended demo", "4/7"),
    ("S015", "Ken", 3, "Missing one root", "4/7"),
    ("S016", "Divya", 3, "Missing one root", "4/7"),
    ("S017", "Bryan", 3, "Sign error â€” recommended demo", "5/7"),
    ("S018", "Mei Ling", 4, "Sign error â€” recommended demo", "4/7"),
    ("S019", "Arjun", 3, "Missing one root", "4/7"),
    ("S020", "Chloe", 3, "Sign error â€” recommended demo", "4/7"),
    ("S021", "Haziq", 4, "Sign error â€” recommended demo", "4/7"),
    ("S022", "Yi Ting", 4, "Sign error â€” recommended demo", "4/7"),
    ("S023", "Nadia", 3, "Sign error â€” recommended demo", "4/7"),
    ("S024", "Ryan", 4, "Sign error â€” recommended demo", "4/7"),
    ("S025", "Shreya", 3, "Sign error â€” recommended demo", "Check"),
    ("S029", "Vikram", 1, "Missing one root", "Check"),
    ("S030", "Serene", 1, "Sign error â€” recommended demo", "Check"),
)
SIGN_ERROR_FIXTURE = next(iter(DEMO_SUBMISSIONS))
STUDENTS_BY_ID = {
    submission_id: {
        "submission_id": submission_id,
        "name": name,
        "steps": steps,
        "fixture": SIGN_ERROR_FIXTURE if fixture.startswith("Sign error") else fixture,
        "status": status,
    }
    for submission_id, name, steps, fixture, status in STUDENT_QUEUE
}


st.set_page_config(
    page_title="AIMS · Lecturer Review",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
    :root {
        --ink: #102a35;
        --ink-soft: #50656b;
        --paper: #f3eee3;
        --surface: #fffdf8;
        --surface-soft: #e8dfd1;
        --coral: #d95749;
        --teal: #267566;
        --gold: #a97812;
        --line: rgba(16, 42, 53, 0.17);
    }
    .stApp {
        background:
            linear-gradient(90deg, rgba(16,42,53,.022) 1px, transparent 1px),
            var(--paper);
        background-size: 30px 30px, auto;
        color: var(--ink);
    }
    html, body, [class*="css"] { font-family: "Trebuchet MS", sans-serif; }
    h1, h2, h3 { font-family: Georgia, "Times New Roman", serif !important; letter-spacing: -.02em; }
    header[data-testid="stHeader"] { display: none; }
    [data-testid="stToolbar"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
    *, *::before, *::after { box-sizing: border-box; }
    p, small, label, [data-testid="stCaptionContainer"] { overflow-wrap: anywhere; }
    .block-container {
        width: 100%; max-width: none;
        padding: clamp(.65rem, 1.2vw, 1rem) clamp(.65rem, 1.15vw, 1.35rem) 1.4rem;
    }
    .block-container [data-testid="stVerticalBlock"] { gap: .68rem; }
    .block-container [data-testid="stHorizontalBlock"] { gap: clamp(.65rem, 1vw, 1rem); }
    [data-testid="stColumn"] { min-width: 0; }

    .st-key-aims_topbar {
        padding: .68rem .85rem;
        border-radius: 9px;
        background: var(--ink);
        box-shadow: 0 8px 24px rgba(16,42,53,.14);
    }
    .st-key-aims_topbar [data-testid="stHorizontalBlock"] { align-items: center; gap: 1rem; }
    .st-key-aims_topbar p, .st-key-aims_topbar span, .st-key-aims_topbar small { color: #f8f3e9 !important; }
    .aims-brand { font: 700 1.35rem/1 Georgia, serif; letter-spacing: .05em; color: #f8f3e9; }
    .aims-assignment { color: #f8f3e9; font-weight: 700; }
    .aims-assignment small { display:block; margin-top:.2rem; color: rgba(248,243,233,.7); font-weight:400; line-height:1.3; text-decoration:none; }
    .aims-status {
        display: inline-block; padding: .3rem .58rem; border: 1px solid rgba(248,243,233,.28);
        border-radius: 999px; color: #f8f3e9; white-space: nowrap;
    }
    .st-key-aims_topbar .stButton > button {
        min-height: 2.2rem; border: 1px solid var(--coral); border-radius: 5px;
        background: var(--coral); color: #fff !important; font-weight: 700;
    }
    .st-key-aims_topbar .stButton > button:disabled { opacity: .48; }
    .st-key-aims_topbar .stButton > button p { color: inherit !important; }

    [data-testid="stExpander"] {
        border-color: var(--line); border-radius: 6px; background: rgba(255,253,248,.56);
    }
    [data-testid="stExpander"] summary { min-height: 2.25rem; }

    .st-key-queue_panel,
    .st-key-submission_panel,
    .st-key-review_panel {
        padding: clamp(.75rem, 1.2vw, 1rem) !important;
        background: rgba(255,253,248,.76);
        border-color: var(--line) !important;
        border-radius: 8px !important;
        box-shadow: 0 10px 32px rgba(16,42,53,.07);
    }
    .st-key-queue_panel {
        padding: .7rem .48rem !important;
        background: rgba(255,253,248,.84);
    }
    .st-key-submission_panel { background: rgba(232,223,209,.65); }
    .panel-title { padding:.05rem .1rem .62rem; font: 700 1.12rem/1.2 Georgia, serif; color: var(--ink); }
    .panel-title small { display:block; margin-top:.25rem; font: 400 .78rem/1.35 "Trebuchet MS", sans-serif; color: var(--ink-soft); }
    .st-key-review_header { padding: .05rem .1rem .25rem !important; }
    .st-key-review_header [data-testid="stHorizontalBlock"] { align-items:center; }
    .st-key-review_header [data-testid="stCaptionContainer"] { margin:0; text-align:right; line-height:1.35; }

    .compact-paper {
        min-height: 405px; padding: 2rem 2rem 1.4rem 3.5rem;
        border: 1px solid var(--line);
        background:
            linear-gradient(90deg, transparent 40px, rgba(217,87,73,.28) 41px, transparent 42px),
            repeating-linear-gradient(#fffefb 0 31px, #c9dce4 32px);
        box-shadow: 0 8px 24px rgba(16,42,53,.09);
        overflow: hidden;
    }
    .compact-handwriting { font: 1.03rem/2 "Segoe Print", "Comic Sans MS", cursive; color: #263f67; }
    .compact-handwriting div { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .source-caption { margin-top:.3rem; color:var(--ink-soft); font-size:.78rem; }
    .student-provenance {
        display:flex; justify-content:space-between; align-items:center; gap:.45rem;
        margin:-.15rem 0 .55rem; padding:.48rem .58rem; border:1px solid var(--line);
        border-radius:6px; background:rgba(255,253,248,.58); line-height:1.25;
    }
    .student-provenance b { display:block; font-size:.82rem; }
    .student-provenance small { color:var(--ink-soft); font-size:.69rem; }
    .student-provenance span {
        flex:none; padding:.18rem .36rem; border-radius:999px;
        background:rgba(169,120,18,.12); color:#795a12; font-size:.63rem; font-weight:700;
    }

    .queue-title {
        display:flex; justify-content:space-between; gap:.35rem; align-items:center;
        padding:.08rem .2rem .5rem; color:var(--ink-soft); font-size:.66rem;
        font-weight:700; letter-spacing:.08em; text-transform:uppercase;
    }
    .queue-summary {
        margin:0 .16rem .45rem; padding:.42rem .48rem; border-radius:5px;
        background:rgba(38,117,102,.08); color:var(--ink-soft); font-size:.66rem; line-height:1.35;
    }
    .st-key-queue_scroll { padding-right:.12rem; }
    .st-key-queue_scroll [data-testid="stVerticalBlock"] { gap:.22rem; }
    [class*="st-key-queue_student_"] { margin:0 !important; }
    [class*="st-key-queue_student_"] .stButton > button {
        min-height:2.45rem; padding:.34rem .42rem; justify-content:flex-start;
        border:1px solid transparent; border-radius:6px; background:transparent;
        box-shadow:none; text-align:left; font-size:.68rem; line-height:1.2;
    }
    [class*="st-key-queue_student_"] .stButton > button:hover {
        border-color:var(--line); background:rgba(232,223,209,.55);
    }
    [class*="st-key-queue_student_"] .stButton > button[kind="primary"] {
        border-color:rgba(38,117,102,.55); background:rgba(38,117,102,.12);
        color:var(--ink) !important;
    }
    [class*="st-key-queue_student_"] .stButton > button p {
        width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    }
    .queue-caption { margin:-.26rem .46rem .08rem; color:var(--ink-soft); font-size:.59rem; }
    .queue-caption b { float:right; color:#795a12; font-weight:700; }
    .camera-placeholder {
        margin-top:.45rem; padding:.45rem .55rem; border:1px dashed var(--line);
        border-radius:6px; color:var(--ink-soft); background:rgba(255,253,248,.45);
        font-size:.69rem; text-align:center;
    }

    [data-testid="stFileUploaderDropzone"] {
        min-height: 4.4rem; padding: .55rem; border-color: var(--line); background: rgba(255,253,248,.82);
    }
    [data-testid="stFileUploaderDropzoneInstructions"] { padding: 0; }
    [data-testid="stFileUploaderDropzone"] button { min-height: 2rem; background: var(--ink); color:#fff !important; }
    [data-testid="stImage"] img { max-height: 470px; object-fit: contain; background: var(--surface); }

    [data-testid="stSegmentedControl"] { margin:.05rem 0 .35rem; }
    [data-testid="stSegmentedControl"] button { min-height: 2.2rem; padding-inline:.7rem; }
    [data-testid="stTextInput"] input { min-height: 2.35rem; padding:.45rem .7rem; background: var(--surface); color:var(--ink); }
    [data-testid="stNumberInput"] input { min-height: 2rem; text-align:center; }
    [data-testid="stCheckbox"] { min-height: 2.1rem; }
    [data-testid="stMain"] label, [data-testid="stMain"] label p { color: var(--ink) !important; }

    .transcript-source {
        display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between;
        gap:.35rem 1rem; padding:.6rem .75rem; margin:.1rem 0 .45rem;
        border-left:3px solid var(--teal); border-radius:0 5px 5px 0;
        background:rgba(38,117,102,.09); color:var(--ink); line-height:1.35;
    }
    .transcript-source small { color:var(--ink-soft); }
    [class*="st-key-transcript_line_"] {
        margin:.25rem 0; padding:.5rem .6rem !important;
        border:1px solid var(--line); border-radius:7px; background:rgba(255,253,248,.62);
    }
    [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] {
        align-items:center; gap:clamp(.6rem, 1vw, 1rem);
    }
    .line-badge { padding:0; color:var(--ink); font-weight:700; line-height:2.35rem; }
    [class*="st-key-line_preview_"] {
        min-height:2.65rem; padding:.3rem .55rem !important;
        display:flex; align-items:center; justify-content:center;
        border-left:1px solid var(--line); overflow:hidden;
    }
    [class*="st-key-line_preview_"] [data-testid="stLatex"] { width:100%; overflow-x:auto; overflow-y:hidden; }
    [class*="st-key-line_preview_"] .katex-display { margin:.1rem 0 !important; }
    .line-preview-empty { width:100%; color:var(--ink-soft); font-size:.78rem; text-align:center; }
    .st-key-transcript_actions {
        margin-top:.65rem; padding:.7rem .2rem .1rem !important; border-top:1px solid var(--line);
    }
    .st-key-transcript_actions [data-testid="stHorizontalBlock"] { align-items:center; }
    .st-key-transcript_actions [data-testid="stCaptionContainer"] { margin-top:.15rem; line-height:1.4; }

    .score-summary {
        min-height: 70px; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between;
        gap:.7rem 1.1rem; padding:.65rem .75rem; border:1px solid var(--line);
        border-radius:6px; background:rgba(232,223,209,.34);
    }
    .score-large { font:700 1.9rem/1 Georgia,serif; color:var(--ink); white-space:nowrap; }
    .score-large small { display:block; margin-top:.18rem; font:400 .7rem/1.15 "Trebuchet MS",sans-serif; color:var(--ink-soft); }
    .divergence-note { flex:1 1 300px; padding:.55rem .65rem; border-left:3px solid var(--coral); background:rgba(217,87,73,.08); color:var(--ink); line-height:1.35; }
    .divergence-note small { color:var(--ink-soft); }

    .step-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.5rem; margin:.5rem 0; }
    .step-chip { min-width:0; padding:.5rem .55rem; border-top:3px solid var(--teal); background:var(--paper); }
    .step-chip.error { border-top-color:var(--coral); }
    .step-chip.carried, .step-chip.method { border-top-color:var(--gold); }
    .step-chip.unverified { border-top-color:var(--gold); }
    .step-chip b { display:block; color:var(--ink); }
    .step-chip small { display:block; margin-top:.15rem; color:var(--ink-soft); line-height:1.3; }

    .rubric-header {
        display:grid; grid-template-columns:minmax(0,2.2fr) minmax(0,.8fr) .65fr 1.35fr;
        gap:.55rem; padding:.35rem .25rem .5rem; border-bottom:1px solid var(--line);
        color:var(--ink-soft); font-size:.75rem; text-transform:uppercase; letter-spacing:.06em;
    }
    .st-key-marking_decision { margin-top:.55rem; }
    .st-key-rubric_table, .st-key-feedback_panel {
        padding:.7rem !important; border-color:var(--line) !important;
        border-radius:7px !important; background:rgba(255,253,248,.72);
    }
    .st-key-feedback_panel label { margin-bottom:.35rem; font-weight:700; }
    .st-key-feedback_panel textarea { padding:.7rem .75rem; line-height:1.45; }
    .rubric-criterion { padding-top:.35rem; color:var(--ink); font-size:.88rem; font-weight:700; line-height:1.25; }
    .rubric-evidence { color:var(--ink-soft); padding-top:.4rem; font-size:.82rem; line-height:1.25; }
    .rubric-recommendation { padding-top:.4rem; text-align:center; color:var(--ink); font-weight:700; }
    .mobile-label { display:none; }
    [class*="st-key-criterion_row_"] { padding:.28rem .15rem .2rem !important; border-bottom:1px solid var(--line); }
    [class*="st-key-criterion_row_"]:last-child { border-bottom:0; }
    [class*="st-key-criterion_row_"] [data-testid="stHorizontalBlock"] { align-items:center; gap:.55rem; }
    [class*="st-key-final_mark_"] [data-testid="stHorizontalBlock"] {
        display:grid !important; grid-template-columns:1.45rem 3.15rem 1.45rem;
        align-items:center; justify-content:end; gap:.18rem !important;
    }
    [class*="st-key-final_mark_"] [data-testid="stColumn"] {
        min-width:0; width:auto !important; flex:none !important;
    }
    [class*="st-key-decrease_mark_"] .stButton > button,
    [class*="st-key-increase_mark_"] .stButton > button {
        width:1.45rem; min-height:2rem; height:2rem; padding:0 !important;
        border:0 !important; border-radius:4px; background:transparent !important; box-shadow:none !important;
    }
    [class*="st-key-decrease_mark_"] .stButton > button:hover,
    [class*="st-key-increase_mark_"] .stButton > button:hover { background:rgba(16,42,53,.08) !important; }
    [class*="st-key-decrease_mark_"] .stButton > button:focus-visible,
    [class*="st-key-increase_mark_"] .stButton > button:focus-visible {
        outline:2px solid var(--teal); outline-offset:1px;
    }
    [class*="st-key-decrease_mark_"] button p,
    [class*="st-key-increase_mark_"] button p { font-size:0; line-height:1; }
    [class*="st-key-decrease_mark_"] button p::before,
    [class*="st-key-increase_mark_"] button p::before {
        display:block; transform:translateY(7px); color:var(--ink);
        font-size:1.08rem; font-weight:700; line-height:1;
    }
    [class*="st-key-decrease_mark_"] button p::before { content:"−"; }
    [class*="st-key-increase_mark_"] button p::before { content:"+"; }
    [class*="st-key-decrease_mark_"] button:disabled p::before,
    [class*="st-key-increase_mark_"] button:disabled p::before { opacity:.35; }
    .mark-value {
        width:3.15rem; min-height:2rem; padding:.15rem .2rem; display:flex; align-items:center; justify-content:center;
        border:1px solid var(--line); border-radius:5px; background:var(--surface-soft); color:var(--ink);
    }
    .mark-value small { margin-left:.08rem; color:var(--ink-soft); font-size:.7rem; }
    .st-key-detailed_checks_panel { margin-top:.75rem; }
    .st-key-detailed_checks_panel [data-testid="stExpander"] { background:rgba(255,253,248,.72); }
    .st-key-detailed_checks_panel [data-testid="stExpanderDetails"] { padding:.75rem .9rem 1rem; }
    .st-key-detailed_checks_panel [data-testid="stExpanderDetails"] p { line-height:1.45; }

    .stButton > button {
        min-height:2.2rem; border-radius:5px; background:var(--surface); border-color:var(--ink);
        color:var(--ink) !important; font-weight:700;
    }
    .stButton > button p { color:inherit !important; }
    .stButton > button[kind="primary"] { background:var(--coral); border-color:var(--coral); color:#fff !important; }
    .review-boundary { padding:.55rem .7rem; border:1px solid rgba(169,120,18,.35); border-radius:5px; background:rgba(169,120,18,.08); color:#624a16; font-size:.86rem; line-height:1.4; }
    .footer-note { padding:.35rem; color:var(--ink-soft); text-align:center; font-size:.76rem; line-height:1.4; }

    @media (max-width: 1360px) {
        [data-testid="stHorizontalBlock"]:has(.st-key-rubric_table):has(.st-key-feedback_panel) {
            flex-wrap:wrap;
        }
        [data-testid="stHorizontalBlock"]:has(.st-key-rubric_table):has(.st-key-feedback_panel) > [data-testid="stColumn"] {
            flex:1 1 100% !important; width:100% !important;
        }
        .st-key-feedback_panel textarea { min-height:7.5rem; }
    }

    [data-testid="stHorizontalBlock"]:has(.st-key-queue_panel):has(.st-key-submission_panel):has(.st-key-review_panel) {
        align-items:stretch; gap:clamp(.4rem,.75vw,.75rem);
    }
    [data-testid="stHorizontalBlock"]:has(.st-key-queue_panel):has(.st-key-submission_panel):has(.st-key-review_panel) > [data-testid="stColumn"] {
        min-width:0;
    }

    @media (max-width: 1180px) {
        .compact-paper { min-height:340px; padding-inline:1rem; padding-left:2.8rem; }
        .st-key-queue_panel,
        .st-key-submission_panel,
        .st-key-review_panel { padding:.62rem !important; }
        .st-key-queue_panel { padding-inline:.35rem !important; }
        [class*="st-key-queue_student_"] .stButton > button { padding-inline:.32rem; font-size:.63rem; }
        .queue-caption { font-size:.55rem; margin-inline:.34rem; }
    }

    @media (max-width: 900px) {
        .st-key-aims_topbar [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
        .st-key-aims_topbar [data-testid="stColumn"]:nth-child(1) { flex:0 0 4.5rem !important; width:4.5rem !important; }
        .st-key-aims_topbar [data-testid="stColumn"]:nth-child(2) { flex:1 1 calc(100% - 5.5rem) !important; width:auto !important; }
        .st-key-aims_topbar [data-testid="stColumn"]:nth-child(3),
        .st-key-aims_topbar [data-testid="stColumn"]:nth-child(4) { flex:1 1 calc(50% - .5rem) !important; width:auto !important; }
        .st-key-review_header [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
        .st-key-review_header [data-testid="stColumn"] { flex:1 1 100% !important; width:100% !important; }
        .st-key-review_header [data-testid="stCaptionContainer"] { text-align:left; }
        .step-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
    }

    @media (max-width: 720px) {
        .block-container { padding:.55rem; }
        .st-key-queue_panel, .st-key-submission_panel, .st-key-review_panel { padding:.7rem !important; }
        .transcript-source { align-items:flex-start; }
        [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
        [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) {
            flex:0 0 2rem !important; width:2rem !important;
        }
        [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {
            flex:1 1 calc(100% - 3rem) !important; width:auto !important;
        }
        [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) {
            flex:1 1 100% !important; width:100% !important; margin-left:2.65rem;
        }
        [class*="st-key-line_preview_"] { border-left:0; border-top:1px solid var(--line); justify-content:flex-start; }
        .st-key-transcript_actions [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
        .st-key-transcript_actions [data-testid="stColumn"] { flex:1 1 100% !important; width:100% !important; }
        .rubric-header { display:none; }
        [class*="st-key-criterion_row_"] [data-testid="stHorizontalBlock"] { flex-wrap:wrap; align-items:flex-start; }
        [class*="st-key-criterion_row_"] [data-testid="stColumn"]:nth-child(1) { flex:1 1 100% !important; width:100% !important; }
        [class*="st-key-criterion_row_"] [data-testid="stColumn"]:nth-child(n+2) { flex:1 1 calc(33.333% - .5rem) !important; width:auto !important; }
        .rubric-evidence, .rubric-recommendation { padding-top:.2rem; text-align:left; }
        .mobile-label, [class*="st-key-final_mark_"]::before {
            display:block; margin-bottom:.2rem; color:var(--ink-soft); font-size:.68rem;
            font-weight:400; text-transform:uppercase; letter-spacing:.05em;
        }
        [class*="st-key-final_mark_"]::before { content:"Final"; }
        .compact-paper { min-height:300px; padding-left:3rem; }
    }

    @media (min-width: 621px) and (max-width: 820px) {
        [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
        [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) {
            flex:0 0 1.7rem !important; width:1.7rem !important;
        }
        [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) {
            flex:1 1 calc(100% - 2.2rem) !important; width:auto !important;
        }
        [class*="st-key-transcript_line_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) {
            display:none;
        }
        .st-key-transcript_actions [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
        .st-key-transcript_actions [data-testid="stColumn"] { flex:1 1 100% !important; width:100% !important; }
        .rubric-header { display:none; }
        [class*="st-key-criterion_row_"] [data-testid="stHorizontalBlock"] { flex-wrap:wrap; align-items:flex-start; }
        [class*="st-key-criterion_row_"] [data-testid="stColumn"]:nth-child(1) { flex:1 1 100% !important; width:100% !important; }
        [class*="st-key-criterion_row_"] [data-testid="stColumn"]:nth-child(n+2) { flex:1 1 calc(33.333% - .5rem) !important; width:auto !important; }
        .mobile-label, [class*="st-key-final_mark_"]::before {
            display:block; margin-bottom:.2rem; color:var(--ink-soft); font-size:.68rem;
            font-weight:400; text-transform:uppercase; letter-spacing:.05em;
        }
        [class*="st-key-final_mark_"]::before { content:"Final"; }
    }

    @media (max-width: 480px) {
        .st-key-aims_topbar [data-testid="stColumn"]:nth-child(3),
        .st-key-aims_topbar [data-testid="stColumn"]:nth-child(4) { flex:1 1 100% !important; width:100% !important; }
        .aims-status { display:block; width:100%; text-align:center; }
        .step-strip { grid-template-columns:1fr; }
        .score-large { font-size:1.7rem; }
        .divergence-note { flex-basis:100%; }
    }

    @media (max-width: 620px) {
        [data-testid="stHorizontalBlock"]:has(.st-key-queue_panel):has(.st-key-submission_panel):has(.st-key-review_panel) {
            flex-wrap:wrap; align-items:flex-start;
        }
        [data-testid="stHorizontalBlock"]:has(.st-key-queue_panel):has(.st-key-submission_panel):has(.st-key-review_panel) > [data-testid="stColumn"] {
            flex:1 1 100% !important; width:100% !important;
        }
        [data-testid="stHorizontalBlock"]:has(.st-key-queue_panel):has(.st-key-submission_panel):has(.st-key-review_panel) > [data-testid="stColumn"]:first-child,
        .st-key-queue_panel { flex:0 0 auto !important; height:auto !important; }
        .st-key-queue_panel > [data-testid="stLayoutWrapper"]:has(.st-key-queue_scroll) {
            flex:0 0 12rem !important; height:12rem !important;
        }
        .st-key-queue_scroll { max-height:12rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def clear_review_state() -> None:
    st.session_state.pop("analysis", None)
    st.session_state.pop("review_feedback", None)
    st.session_state.pop("approved_review_signature", None)
    for key in tuple(st.session_state):
        if key.startswith("mark_") or key == "rubric_editor":
            del st.session_state[key]


def activate_transcript(source_id: str, initial_steps: tuple[str, ...]) -> bool:
    """Reset transcript and review state when the displayed submission changes."""
    if st.session_state.get("transcript_source_id") == source_id:
        return False
    st.session_state["transcript_source_id"] = source_id
    for index in range(1, 5):
        st.session_state[f"line_{index}"] = initial_steps[index - 1]
    st.session_state["confirmed_transcript"] = False
    st.session_state["workspace_view"] = "Transcript"
    clear_review_state()
    return True


def select_submission(submission_id: str) -> None:
    """Open a seeded student script from the lecturer queue."""
    student = STUDENTS_BY_ID[submission_id]
    fixture = student["fixture"]
    st.session_state["selected_submission_id"] = submission_id
    st.session_state["submission_source_mode"] = "Prepared example"
    st.session_state["prepared_submission"] = fixture
    activate_transcript(
        f"student:{submission_id}:demo:{fixture}",
        DEMO_SUBMISSIONS[fixture],
    )


def mark_transcript_dirty() -> None:
    st.session_state["confirmed_transcript"] = False
    st.session_state["workspace_view"] = "Transcript"
    clear_review_state()


def run_analysis() -> None:
    steps = [st.session_state.get(f"line_{index}", "") for index in range(1, 5)]
    result = grade_submission(QUESTION, steps)
    clear_review_state()
    st.session_state["analysis"] = result
    st.session_state["review_feedback"] = result.student_feedback
    st.session_state["workspace_view"] = "Marking review"


def adjust_mark(criterion_id: str, recommended_marks: int, maximum_marks: int, delta: int) -> None:
    """Move a lecturer mark by one point while keeping it inside the rubric range."""
    mark_key = f"mark_{criterion_id}"
    current_mark = int(st.session_state.get(mark_key, recommended_marks))
    st.session_state[mark_key] = max(0, min(maximum_marks, current_mark + delta))


def review_signature(result) -> str:
    """Identify the exact lecturer-editable review that has been approved."""
    values = [st.session_state.get("review_feedback", result.student_feedback)]
    values.extend(
        str(st.session_state.get(f"mark_{criterion.criterion_id}", criterion.recommended_marks))
        for criterion in result.criteria
    )
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def approve_review() -> None:
    result = st.session_state.get("analysis")
    if result is not None:
        st.session_state["approved_review_signature"] = review_signature(result)
        reviewed_scores = dict(st.session_state.get("reviewed_scores", {}))
        reviewed_scores[st.session_state["selected_submission_id"]] = sum(
            st.session_state.get(f"mark_{criterion.criterion_id}", criterion.recommended_marks)
            for criterion in result.criteria
        )
        st.session_state["reviewed_scores"] = reviewed_scores


def safe_latex(value: str) -> str:
    return value.strip().strip("$")


def handwriting_text(value: str) -> str:
    return value.replace(r"\text{ or }", " or ").replace("^2", "²")


if "selected_submission_id" not in st.session_state:
    st.session_state["selected_submission_id"] = "S027"
selected_student = STUDENTS_BY_ID[st.session_state["selected_submission_id"]]
if "prepared_submission" not in st.session_state:
    st.session_state["prepared_submission"] = selected_student["fixture"]

result = st.session_state.get("analysis")
current_final_total = 0
current_review_signature = None
if result:
    current_final_total = sum(
        st.session_state.get(f"mark_{criterion.criterion_id}", criterion.recommended_marks)
        for criterion in result.criteria
    )
    current_review_signature = review_signature(result)

if current_review_signature and st.session_state.get("approved_review_signature") == current_review_signature:
    status_label = f"Approved · {current_final_total}/{result.maximum_total}"
elif result:
    status_label = f"Reviewing · {current_final_total}/{result.maximum_total}"
else:
    status_label = "Transcript pending"


with st.container(key="aims_topbar"):
    brand_col, assignment_col, status_col, approve_col = st.columns((.55, 2.8, 1.05, .95))
    brand_col.markdown('<div class="aims-brand">AIMS</div>', unsafe_allow_html=True)
    assignment_col.markdown(
        (
            '<div class="aims-assignment">Quadratic factorisation'
            f'<small>{html.escape(selected_student["name"])} ({selected_student["submission_id"]}) '
            '· Lecturer marking workspace</small></div>'
        ),
        unsafe_allow_html=True,
    )
    status_col.markdown(f'<span class="aims-status">{status_label}</span>', unsafe_allow_html=True)
    approve_col.button(
        "Approve review",
        use_container_width=True,
        disabled=result is None,
        on_click=approve_review,
    )


with st.expander("Reference · question, model solution and rubric", expanded=False):
    question_col, model_col, rubric_col = st.columns((.9, 1.15, 1.25))
    with question_col:
        st.markdown("**Question**")
        st.latex(QUESTION_DISPLAY)
        st.caption(INSTRUCTION)
    with model_col:
        st.markdown("**Model path**")
        st.latex(MODEL_STEPS[1])
        st.latex(MODEL_STEPS[3])
    with rubric_col:
        st.markdown("**Rubric**")
        st.markdown("  \n".join(f"`{marks}` {title}" for _, title, marks in RUBRIC))


queue_col, document_col, review_col = st.columns((.30, .70, 1.0), gap="small")

with queue_col:
    with st.container(key="queue_panel", border=True):
        st.markdown(
            '<div class="queue-title"><span>Student queue</span><span>30 scripts</span></div>',
            unsafe_allow_html=True,
        )
        reviewed_scores = st.session_state.get("reviewed_scores", {})
        st.markdown(
            f'<div class="queue-summary">{len(reviewed_scores)} reviewed in this session · select a submission to mark</div>',
            unsafe_allow_html=True,
        )
        with st.container(key="queue_scroll", height=515, border=False):
            for submission_id, name, step_count, _fixture, seeded_status in STUDENT_QUEUE:
                is_selected = submission_id == selected_student["submission_id"]
                display_status = (
                    f'{reviewed_scores[submission_id]}/7'
                    if submission_id in reviewed_scores
                    else seeded_status
                )
                with st.container(key=f"queue_student_{submission_id}"):
                    st.button(
                        f"{name} ({submission_id})",
                        key=f"open_submission_{submission_id}",
                        type="primary" if is_selected else "secondary",
                        use_container_width=True,
                        on_click=select_submission,
                        args=(submission_id,),
                    )
                    st.markdown(
                        (
                            f'<div class="queue-caption">{step_count} transcript lines'
                            f'<b>{html.escape(display_status)}</b></div>'
                        ),
                        unsafe_allow_html=True,
                    )

with document_col:
    with st.container(key="submission_panel", border=True):
        st.markdown(
            '<div class="panel-title">Original submission<small>35% · student-uploaded evidence</small></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                '<div class="student-provenance"><div>'
                f'<b>{html.escape(selected_student["name"])} ({selected_student["submission_id"]})</b>'
                '<small>Submitted by student · lecturer review copy</small></div>'
                '<span>Needs review</span></div>'
            ),
            unsafe_allow_html=True,
        )
        source_mode = st.segmented_control(
            "Submission source",
            ("Prepared example", "Upload file"),
            default="Prepared example",
            key="submission_source_mode",
            required=True,
            label_visibility="collapsed",
            width="stretch",
        )
        st.markdown(
            '<div class="camera-placeholder">Camera capture placeholder · planned after prototype review</div>',
            unsafe_allow_html=True,
        )

        sample_label = selected_student["fixture"]
        upload_preview = None
        upload_error = None
        source_changed = False

        if source_mode == "Prepared example":
            sample_label = st.selectbox(
                "Prepared submission",
                tuple(DEMO_SUBMISSIONS),
                key="prepared_submission",
                label_visibility="collapsed",
            )
            source_changed = activate_transcript(
                f'student:{selected_student["submission_id"]}:demo:{sample_label}',
                DEMO_SUBMISSIONS[sample_label],
            )
        else:
            uploaded = st.file_uploader(
                "Upload handwritten working",
                type=("jpg", "jpeg", "png", "pdf"),
                help="Files are rendered locally and are not sent to an OCR service.",
            )
            if uploaded:
                payload = uploaded.getvalue()
                upload_hash = hashlib.sha256(payload).hexdigest()[:12]
                try:
                    total_pages = page_count(uploaded.name, payload)
                    selected_page = 1
                    if total_pages > 1:
                        selected_page = st.selectbox(
                            "PDF page",
                            tuple(range(1, total_pages + 1)),
                            format_func=lambda number: f"Page {number} of {total_pages}",
                            key=f"pdf_page_{upload_hash}",
                            label_visibility="collapsed",
                        )
                    upload_preview = render_preview(uploaded.name, payload, page_number=selected_page)
                    source_changed = activate_transcript(
                        (
                            f'student:{selected_student["submission_id"]}:upload:'
                            f"{uploaded.name}:{upload_hash}:page-{selected_page}"
                        ),
                        ("", "", "", ""),
                    )
                except DocumentPreviewError as exc:
                    upload_error = str(exc)
                    source_changed = activate_transcript("upload:error", ("", "", "", ""))
            else:
                source_changed = activate_transcript(
                    f'student:{selected_student["submission_id"]}:upload:none',
                    ("", "", "", ""),
                )

        if source_changed:
            st.rerun()

        if source_mode == "Prepared example":
            preview_steps = DEMO_SUBMISSIONS[sample_label]
            handwriting = "".join(
                f"<div>{html.escape(handwriting_text(line)) or '&nbsp;'}</div>" for line in preview_steps
            )
            st.markdown(
                f'<div class="compact-paper"><div class="compact-handwriting">{handwriting}</div></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="source-caption">Prepared demonstration · matching extraction fixture loaded</div>',
                unsafe_allow_html=True,
            )
        elif upload_error:
            st.error(upload_error)
        elif upload_preview:
            st.image(
                upload_preview.image,
                caption=(
                    f"{upload_preview.filename} · page {upload_preview.page_number} "
                    f"of {upload_preview.page_count} · rendered locally"
                ),
                use_container_width=True,
            )
        else:
            st.info("Upload a JPG, JPEG, PNG, or PDF to begin.")


with review_col:
    with st.container(key="review_panel", border=True):
        with st.container(key="review_header"):
            title_col, context_col = st.columns((1.1, 1))
            title_col.markdown('<div class="panel-title">Lecturer review</div>', unsafe_allow_html=True)
            transcript_count = sum(bool(st.session_state.get(f"line_{index}", "").strip()) for index in range(1, 5))
            context_col.caption(f"{transcript_count} transcript lines · confirmed source required")

        active_view = st.segmented_control(
            "Review stage",
            ("Transcript", "Marking review"),
            default="Transcript",
            key="workspace_view",
            required=True,
            label_visibility="collapsed",
            width="stretch",
        )

        if active_view == "Transcript":
            source_text = "Prepared extraction" if source_mode == "Prepared example" else "Manual transcription"
            st.markdown(
                f'<div class="transcript-source"><span>{source_text}</span><small>Edit ambiguous symbols before checking.</small></div>',
                unsafe_allow_html=True,
            )

            for index in range(1, 5):
                with st.container(key=f"transcript_line_{index}"):
                    line_col, input_col, preview_col = st.columns((.09, .55, .36))
                    line_col.markdown(f'<div class="line-badge">L{index}</div>', unsafe_allow_html=True)
                    value = input_col.text_input(
                        f"Transcript line {index}",
                        key=f"line_{index}",
                        placeholder="Enter one equation",
                        label_visibility="collapsed",
                        on_change=mark_transcript_dirty,
                    )
                    with preview_col:
                        with st.container(key=f"line_preview_{index}"):
                            if value:
                                st.latex(safe_latex(value))
                            else:
                                st.markdown(
                                    '<div class="line-preview-empty">Preview appears here</div>',
                                    unsafe_allow_html=True,
                                )

            with st.container(key="transcript_actions"):
                confirm_col, action_col = st.columns((1.35, .65))
                confirm_col.checkbox(
                    "Transcript checked against submission",
                    key="confirmed_transcript",
                )
                has_working = any(st.session_state.get(f"line_{index}", "").strip() for index in range(1, 5))
                action_col.button(
                    "Check mathematics",
                    type="primary",
                    use_container_width=True,
                    disabled=not st.session_state.get("confirmed_transcript", False) or not has_working,
                    on_click=run_analysis,
                )
                st.caption("The confirmed transcript—not the image—is the source of truth for marking.")

        elif result is None:
            st.info("Confirm the transcript and check the mathematics to open the marking review.")
        else:
            final_total = sum(
                st.session_state.get(f"mark_{criterion.criterion_id}", criterion.recommended_marks)
                for criterion in result.criteria
            )
            divergence_title, divergence_text = divergence_summary(result)
            st.markdown(
                f"""
                <div class="score-summary">
                  <div class="score-large">{result.recommended_total}/{result.maximum_total}<small>System recommendation · lecturer final {final_total}/{result.maximum_total}</small></div>
                  <div class="divergence-note"><b>{html.escape(divergence_title)}</b><br><small>{html.escape(divergence_text)}</small></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            step_html = "".join(
                (
                    f'<div class="step-chip {step.tone}"><b>{step.line_id}</b>'
                    f'<small>{html.escape(step.label)}</small></div>'
                )
                for step in present_steps(result.step_checks)
            )
            st.markdown(f'<div class="step-strip">{step_html}</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="review-boundary">Recommendations use the confirmed transcript. Every mark and comment remains editable by the lecturer.</div>',
                unsafe_allow_html=True,
            )

            with st.container(key="marking_decision"):
                rubric_table_col, feedback_col = st.columns((1.62, .78), gap="large")
                with rubric_table_col:
                    with st.container(key="rubric_table", border=True):
                        st.markdown(
                            '<div class="rubric-header"><span>Criterion</span><span>Evidence</span><span>System</span><span>Final</span></div>',
                            unsafe_allow_html=True,
                        )
                        for criterion in result.criteria:
                            with st.container(key=f"criterion_row_{criterion.criterion_id}"):
                                criterion_col, evidence_col, recommendation_col, mark_col = st.columns((2.2, .8, .65, 1.35))
                                criterion_col.markdown(
                                    f'<div class="rubric-criterion">{html.escape(criterion.title)}</div>',
                                    unsafe_allow_html=True,
                                )
                                evidence = ", ".join(criterion.evidence_line_ids) or "Review"
                                evidence_col.markdown(
                                    f'<div class="rubric-evidence"><span class="mobile-label">Evidence</span>{html.escape(evidence)}</div>',
                                    unsafe_allow_html=True,
                                )
                                recommendation_col.markdown(
                                    f'<div class="rubric-recommendation"><span class="mobile-label">System</span>{criterion.recommended_marks}/{criterion.max_marks}</div>',
                                    unsafe_allow_html=True,
                                )
                                with mark_col:
                                    with st.container(key=f"final_mark_{criterion.criterion_id}"):
                                        mark_key = f"mark_{criterion.criterion_id}"
                                        if mark_key not in st.session_state:
                                            st.session_state[mark_key] = criterion.recommended_marks
                                        current_mark = int(st.session_state[mark_key])
                                        minus_col, mark_value_col, plus_col = st.columns((1, 1.15, 1), gap="small")
                                        minus_col.button(
                                            f"Decrease mark for {criterion.title}",
                                            key=f"decrease_mark_{criterion.criterion_id}",
                                            disabled=current_mark <= 0,
                                            on_click=adjust_mark,
                                            args=(
                                                criterion.criterion_id,
                                                criterion.recommended_marks,
                                                criterion.max_marks,
                                                -1,
                                            ),
                                            use_container_width=True,
                                        )
                                        mark_value_col.markdown(
                                            f'<div class="mark-value"><b>{current_mark}</b><small>/{criterion.max_marks}</small></div>',
                                            unsafe_allow_html=True,
                                        )
                                        plus_col.button(
                                            f"Increase mark for {criterion.title}",
                                            key=f"increase_mark_{criterion.criterion_id}",
                                            disabled=current_mark >= criterion.max_marks,
                                            on_click=adjust_mark,
                                            args=(
                                                criterion.criterion_id,
                                                criterion.recommended_marks,
                                                criterion.max_marks,
                                                1,
                                            ),
                                            use_container_width=True,
                                        )

                with feedback_col:
                    with st.container(key="feedback_panel", border=True):
                        st.text_area(
                            "Editable feedback",
                            key="review_feedback",
                            height=285,
                        )

                with st.container(key="detailed_checks_panel"):
                    with st.expander("Detailed checks", expanded=False):
                        rubric_detail_col, working_detail_col = st.columns(2, gap="large")
                        with rubric_detail_col:
                            st.markdown("**Rubric explanations**")
                            for criterion in result.criteria:
                                st.markdown(f"**{criterion.title}** — {criterion.rationale}")
                        with working_detail_col:
                            st.markdown("**Working-line checks**")
                            for presentation, check in zip(present_steps(result.step_checks), result.step_checks):
                                roots = f" · roots: {', '.join(check.roots)}" if check.roots else ""
                                st.markdown(f"**{check.line_id} · {presentation.label}** — {check.explanation}{roots}")
                            st.markdown("**What was done well**")
                            for item in result.strengths:
                                st.write(f"✓ {item}")
                            st.markdown("**Priority for improvement**")
                            for item in result.priorities:
                                st.write(f"→ {item}")


st.markdown(
    '<div class="footer-note">AIMS prototype · Files rendered locally · Recommendations require lecturer approval</div>',
    unsafe_allow_html=True,
)
