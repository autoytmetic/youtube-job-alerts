"""
src/script_generator.py — Generates unique 100-130 word narration scripts
for each job alert video using varied templates.
"""

import re
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Hook Templates ─────────────────────────────────────────────────────────────
HOOKS = [
    "Big opportunity alert! If you are looking for a government job in India, listen carefully.",
    "Attention job seekers! A major recruitment has just been announced. Don't miss this chance.",
    "Breaking news for all job aspirants! A fresh vacancy is now open. Here are the full details.",
    "Great news for all graduates! A new government job notification is out. Check this now.",
    "Stop scrolling! This is one of the best job opportunities of 2026. Watch till the end.",
    "Sarkari naukri alert! A new recruitment drive has been launched. Here is everything you need to know.",
    "Are you searching for a stable government job? Your wait might be over. Listen to this update.",
    "Huge vacancy alert! Thousands of posts are now open across India. Apply before the deadline.",
]

# ── Salary Emphasis Templates ──────────────────────────────────────────────────
SALARY_LINES = [
    "The salary for this post is {salary}, plus full government benefits.",
    "Selected candidates will earn {salary} per month along with allowances.",
    "This post offers a pay scale of {salary} with job security and pension.",
    "You will receive {salary} monthly, with HRA, DA, and medical benefits included.",
    "The monthly pay package is {salary}, making this a highly attractive position.",
]

# ── Deadline Urgency Templates ─────────────────────────────────────────────────
DEADLINE_LINES = [
    "The last date to apply is {deadline}, so do not wait.",
    "Hurry up! Applications close on {deadline}. Apply today itself.",
    "You have until {deadline} to submit your application. Time is running out.",
    "The deadline is {deadline}. Miss it and you miss the opportunity.",
    "Last date is {deadline}. Act fast before the window closes.",
]

# ── CTA Templates ──────────────────────────────────────────────────────────────
CTAS = [
    "Visit the official website now and submit your application. Link is in the description.",
    "Click the link in the description to apply online. Do not delay.",
    "For complete details and to apply, check the official link given below.",
    "Apply now through the official portal. All details are in the description below.",
    "Don't forget to like this video and subscribe for daily job alerts. Apply via the link below.",
    "Share this with your friends who need a job. Apply link is in the description.",
]

# ── Eligibility Lines ─────────────────────────────────────────────────────────
ELIGIBILITY_PREFIXES = [
    "Candidates with a minimum qualification of",
    "The eligibility for this post requires",
    "Applicants who have completed",
    "This recruitment is open for candidates having",
]


class ScriptGenerator:
    """Generates unique narration scripts for job alert videos."""

    def generate(self, job: dict) -> str:
        """
        Create a ~110-word script for the given job.
        Returns a plain text string suitable for TTS.
        """
        title    = self._clean(job.get("title",   "Government Job Vacancy"))
        company  = self._clean(job.get("company", "Government of India"))
        salary   = self._clean(job.get("salary",  "as per government norms"))
        deadline = self._clean(job.get("deadline","very soon"))
        source   = job.get("source", "")

        # ── Build script sections ──────────────────────────────────────────
        hook      = random.choice(HOOKS)
        sal_line  = random.choice(SALARY_LINES).format(salary=salary)
        dead_line = random.choice(DEADLINE_LINES).format(deadline=deadline)
        cta       = random.choice(CTAS)
        elig_pfx  = random.choice(ELIGIBILITY_PREFIXES)

        # Determine qualification hint from title
        qual = self._detect_qualification(title)

        # ── Assemble ───────────────────────────────────────────────────────
        script = (
            f"{hook} "
            f"{company} has announced a new recruitment for {title}. "
            f"{elig_pfx} {qual} are eligible to apply. "
            f"{sal_line} "
            f"{dead_line} "
            f"This is a great chance to secure a stable government career. "
            f"{cta}"
        )

        script = self._normalize_whitespace(script)
        word_count = len(script.split())

        # ── Pad if too short ───────────────────────────────────────────────
        if word_count < 100:
            script += (
                " This job comes with all government perks including provident fund, "
                "medical insurance, and paid leave. A golden opportunity for deserving candidates."
            )

        # ── Trim if too long ───────────────────────────────────────────────
        words = script.split()
        if len(words) > 135:
            script = " ".join(words[:130]) + "."

        logger.debug(f"Script ({len(script.split())} words) generated.")
        return script

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        """Remove brackets, extra spaces, special chars for clean TTS."""
        text = re.sub(r"\(.*?\)", "", text)          # remove parentheses
        text = re.sub(r"\[.*?\]", "", text)          # remove brackets
        text = re.sub(r"[₹\*\#\@\!]", "", text)     # strip symbols (TTS will say "rupees")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _detect_qualification(title: str) -> str:
        """Infer minimum qualification from job title keywords."""
        t = title.lower()
        if any(k in t for k in ["10th", "matriculation", "matric", "class 10"]):
            return "10th pass"
        if any(k in t for k in ["12th", "intermediate", "higher secondary", "class 12"]):
            return "12th pass"
        if any(k in t for k in ["engineer", "b.tech", "btech", "be ", "b.e"]):
            return "B.Tech or B.E. degree holders"
        if any(k in t for k in ["mba", "management"]):
            return "MBA graduates"
        if any(k in t for k in ["doctor", "mbbs", "medical officer"]):
            return "MBBS or medical degree holders"
        if any(k in t for k in ["law", "legal", "advocate"]):
            return "LLB graduates"
        if any(k in t for k in ["iti", "diploma", "polytechnic"]):
            return "ITI or Diploma holders"
        # Default
        return "graduates from any recognized university"
