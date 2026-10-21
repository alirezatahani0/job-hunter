from __future__ import annotations

import os
from pathlib import Path

from job_assistant.services.employer_form import (
    APPLICANT_CITY,
    APPLICANT_COUNTRY,
    APPLICANT_EMAIL,
    APPLICANT_FIRST,
    APPLICANT_LAST,
    APPLICANT_LINKEDIN,
    applicant_phone,
    classify_apply_url,
    failed,
    pick_location,
    remember_apply_link,
    resolve_apply_url,
    succeeded,
)
from job_assistant.services.resume_pdf import docx_to_pdf

PROFILE_DIR = Path("output") / "chrome-apply-profile"


def submit_application(
    posting_url: str,
    *,
    resume_path: str | Path,
    cover_path: str | Path | None = None,
    client=None,
    opener=None,
) -> dict:
    """Open the employer form and send it. A card is Applied only after this returns submitted."""
    resume = Path(resume_path)
    if not resume.exists():
        return failed("resume", f"Resume file is missing: {resume}")
    apply_url = _apply_url(posting_url, client)
    if not apply_url:
        return failed(
            "apply link",
            "Himalayas did not return an employer form. A signed-in Himalayas session is required to open it. "
            f"Posting: {posting_url}",
            needs_you=True,
        )
    if apply_url != posting_url:
        remember_apply_link(posting_url, apply_url)
    kind = classify_apply_url(apply_url)
    open_page = opener or _open
    if kind == "dover":
        pdf_path = _pdf_for(resume)
        return open_page(apply_url, kind="dover", resume_path=pdf_path, cover_path=None)
    if kind == "recruitee":
        return open_page(
            apply_url,
            kind="recruitee",
            resume_path=resume,
            cover_path=Path(cover_path) if cover_path else None,
        )
    if kind == "wellfound":
        return open_page(apply_url, kind="wellfound", resume_path=resume, cover_path=None)
    return failed(
        "apply link",
        f"No submitter for this form yet ({kind}). Posting: {apply_url}",
        needs_you=True,
        apply_url=apply_url,
    )


def _apply_url(posting_url: str, client) -> str | None:
    if classify_apply_url(posting_url) != "himalayas":
        return posting_url
    import httpx

    if client is not None:
        return resolve_apply_url(posting_url, client)
    with httpx.Client(timeout=30, follow_redirects=True) as http:
        return resolve_apply_url(posting_url, http)


def _pdf_for(resume: Path) -> Path:
    if resume.suffix.lower() == ".pdf":
        return resume
    pdf_path = resume.with_suffix(".pdf")
    pdf_path.write_bytes(docx_to_pdf(resume))
    return pdf_path


def _open(url: str, *, kind: str, resume_path: Path, cover_path: Path | None) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return failed(
            "browser",
            "Playwright is not installed, so the employer form was not opened.",
            apply_url=url,
        )
    headless = os.getenv("APPLY_HEADLESS", "1").strip() not in {"0", "false", "no"}
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            channel="chrome",
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            if kind == "dover":
                return _submit_dover(page, url, resume_path)
            if kind == "recruitee":
                return _submit_recruitee(page, url, resume_path, cover_path)
            return _submit_wellfound(page, url)
        finally:
            context.close()


def _submit_dover(page, url: str, resume_path: Path) -> dict:
    page.goto(url, wait_until="domcontentloaded")
    page.locator('input[name="firstName"]').fill(APPLICANT_FIRST)
    page.locator('input[name="lastName"]').fill(APPLICANT_LAST)
    page.locator('input[name="email"]').fill(APPLICANT_EMAIL)
    page.locator('input[name="linkedinUrl"]').fill(APPLICANT_LINKEDIN)
    page.locator('input[name="phoneNumber"]').fill(applicant_phone())
    page.locator('input[type="file"]').last.set_input_files(str(resume_path))
    try:
        page.wait_for_function(
            "() => { const el = document.querySelector('input[name=cf-turnstile-response]'); return !!(el && el.value); }",
            timeout=25000,
        )
    except Exception:  # noqa: BLE001
        return failed(
            "captcha",
            "Cloudflare check was not completed on the Dover form, so it was not sent.",
            apply_url=url,
        )
    try:
        with page.expect_response(
            lambda response: "application-portal-inbound-application" in response.url
            and response.request.method == "POST",
            timeout=20000,
        ) as caught:
            page.locator("form").get_by_role("button", name="Apply").click()
        response = caught.value
    except Exception as exc:  # noqa: BLE001
        return failed("submit", f"Dover form was filled but not accepted ({exc}).", apply_url=url)
    if response.status in {200, 201}:
        return succeeded(
            "Submitted the Dover form with name, email, phone, LinkedIn, and the resume PDF. "
            "This form has no cover letter field.",
            apply_url=url,
        )
    return failed(
        "submit",
        f"Dover returned {response.status} and the form was not accepted.",
        apply_url=url,
    )


def _submit_recruitee(page, url: str, resume_path: Path, cover_path: Path | None) -> dict:
    page.goto(url, wait_until="domcontentloaded")
    page.get_by_role("textbox", name="Full name").fill(f"{APPLICANT_FIRST} {APPLICANT_LAST}")
    page.get_by_role("textbox", name="Email address").fill(APPLICANT_EMAIL)
    _fill_phone(page)
    page.locator('input[type="file"][name="candidate.cv"]').set_input_files(str(resume_path))
    if cover_path and cover_path.exists():
        page.locator('input[type="file"][name="candidate.coverLetterFile"]').set_input_files(str(cover_path))
    location = _choose_recruitee_location(page)
    if location is None:
        return failed(
            "location",
            f"The form asks for a work location and {APPLICANT_CITY}, {APPLICANT_COUNTRY} is not one of the choices.",
            needs_you=True,
            apply_url=url,
        )
    try:
        with page.expect_response(
            lambda response: response.request.method == "POST" and response.url.rstrip("/").endswith("/candidates"),
            timeout=25000,
        ) as caught:
            page.get_by_role("button", name="Send").click()
        response = caught.value
    except Exception:  # noqa: BLE001
        return failed(
            "captcha",
            "The Recruitee form was filled, but the captcha was not completed, so it was not sent.",
            apply_url=url,
        )
    if response.status in {200, 201}:
        return succeeded("Submitted the Recruitee form with the resume and cover letter.", apply_url=url)
    return failed(
        "submit",
        f"Recruitee returned {response.status} and the form was not accepted.",
        apply_url=url,
    )


def _fill_phone(page) -> None:
    phone = page.get_by_role("textbox", name="Phone number")
    phone.fill(applicant_phone())


def _choose_recruitee_location(page) -> dict | None:
    boxes = page.locator('input[name="candidate.locations.value"]')
    options = []
    count = boxes.count()
    for index in range(count):
        box = boxes.nth(index)
        label = box.evaluate(
            """el => {
                const node = el.labels && el.labels[0];
                return (node && node.innerText || el.getAttribute('aria-label') || '').trim();
            }"""
        )
        options.append({"value": box.get_attribute("value") or "", "label": label, "index": index})
    chosen = pick_location(options)
    if chosen is None:
        return None
    box = boxes.nth(chosen["index"])
    box.evaluate("el => el.click()")
    return chosen


def _submit_wellfound(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded")
    body = page.inner_text("body")[:1500].lower()
    if "log in" in body or "sign up" in body or "sign in" in body or "set a password" in body:
        return failed(
            "login",
            "Wellfound asks for a new account password before it will take the application. The form was not sent. "
            f"Posting: {url}",
            needs_you=True,
            apply_url=url,
        )
    return failed(
        "apply link",
        f"Wellfound did not show a form this submitter can send. Posting: {url}",
        needs_you=True,
        apply_url=url,
    )
