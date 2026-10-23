"""Read the signed-in Google account in Mail. The scheduled job uses this."""

from __future__ import annotations

import subprocess

from job_assistant.services.mail import MailMessage, decide

_ACCOUNT = r'''
on applicantAccount()
  tell application "Mail"
    repeat with oneAccount in accounts
      try
        if (email addresses of oneAccount as string) contains "alireza.tahani01@gmail.com" then return oneAccount
      end try
    end repeat
  end tell
  error "Sign in to alireza.tahani01@gmail.com in Mail"
end applicantAccount
'''

_HEADERS = r'''
tell application "Mail"
  set theAccount to my applicantAccount()
  check for new mail for theAccount
  set theBox to mailbox "INBOX" of theAccount
  set output to ""
  repeat with i from 1 to 20
    try
      set m to message i of theBox
    on error
      exit repeat
    end try
    set mid to id of m as string
    set fromAddr to my one_line(sender of m)
    set subj to my one_line(subject of m)
    set output to output & mid & tab & fromAddr & tab & subj & linefeed
  end repeat
  return output
end tell

on one_line(value)
  set AppleScript's text item delimiters to {return, linefeed, tab}
  set parts to text items of (value as string)
  set AppleScript's text item delimiters to " "
  set flattened to parts as string
  set AppleScript's text item delimiters to ""
  return flattened
end one_line
''' + _ACCOUNT

_BODY = r'''
tell application "Mail"
  set theAccount to my applicantAccount()
  set m to first message of mailbox "INBOX" of theAccount whose id is MESSAGE_ID
  set bodyText to content of m
  if length of bodyText > 800 then set bodyText to text 1 thru 800 of bodyText
  return bodyText
end tell
''' + _ACCOUNT


def fetch_recent_mail() -> list[MailMessage]:
    headers = _run(_HEADERS, timeout=90)
    messages: list[MailMessage] = []
    for line in headers.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 3 or not parts[0].strip():
            continue
        message = MailMessage(
            message_id=parts[0].strip(),
            sender=parts[1].strip(),
            subject=parts[2].strip(),
            body="",
        )
        if _needs_body(message) and message.message_id.isdigit():
            try:
                body = _run(_BODY.replace("MESSAGE_ID", message.message_id), timeout=25)
                message = MailMessage(
                    message_id=message.message_id,
                    sender=message.sender,
                    subject=message.subject,
                    body=_one_line(body),
                )
            except RuntimeError:
                pass
        messages.append(message)
    return messages


def _needs_body(message: MailMessage) -> bool:
    """Open the body when the subject might be an application, a rejection, or an invite."""
    if decide(message) in {"rejection", "interview", "question"}:
        return True
    text = f"{message.subject} {message.sender}".lower()
    return any(
        word in text
        for word in ("apply", "application", "interview", "candidate", "unfortunately", "regret")
    )


def _one_line(value: str) -> str:
    return " ".join(value.split())


def reply_in_mail(message_id: str, body: str) -> None:
    if not str(message_id).isdigit():
        raise RuntimeError("Mail could not match that message.")
    safe_body = body.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Mail"
  set theAccount to my applicantAccount()
  set m to first message of mailbox "INBOX" of theAccount whose id is {int(message_id)}
  set r to reply m without opening window
  set content of r to "{safe_body}"
  send r
end tell
''' + _ACCOUNT
    _run(script, timeout=60)


def _run(script: str, timeout: int) -> str:
    completed = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Mail did not answer").strip()
        if "execution error:" in detail:
            detail = detail.split("execution error:", 1)[1]
        detail = detail.split("(-")[0].strip()
        raise RuntimeError(detail[:300] or "Mail did not answer")
    return completed.stdout or ""
