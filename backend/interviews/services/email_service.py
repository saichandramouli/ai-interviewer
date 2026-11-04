"""
Candidate interview invitation email templates and builders.
"""
from typing import Optional


def build_candidate_invitation_subject(job_title: str) -> str:
    return f"Invitation to Attend Your AI Interview: {job_title}"


def build_candidate_invitation_body(
    candidate_name: str,
    job_title: str,
    organization_name: str,
    candidate_url: str,
    expires_at_str: str,
) -> str:
    """
    Constructs clean, professional plain-text candidate invitation email body.
    """
    org_line = f"with {organization_name} " if organization_name else ""
    return f"""Dear {candidate_name},

You have been invited to complete a browser-based AI interview for the {job_title} position {org_line}.

Your interview is conducted through an AI-assisted conversational interface. Please find your personal interview link below:

{candidate_url}

IMPORTANT DETAILS & INSTRUCTIONS:
- Expiration: This interview link is valid until {expires_at_str}.
- Duration: Please allocate approximately 30 minutes in a quiet environment.
- Hardware: A working microphone and headphones/speakers are required.
- Browser: Please use a modern desktop browser (Chrome, Edge, Firefox, or Safari).
- Permissions: You will be asked to grant microphone permissions when entering the portal.

If you experience any difficulties or have questions regarding your application, please reach out to your recruiting team.

Best regards,
{organization_name or 'Talent Acquisition Team'}
"""


def build_candidate_invitation_html(
    candidate_name: str,
    job_title: str,
    organization_name: str,
    candidate_url: str,
    expires_at_str: str,
) -> str:
    """
    Constructs a responsive HTML email for the candidate invitation.
    """
    org_title = organization_name or "Talent Acquisition Team"
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Invitation to Attend Your AI Interview</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9f9f9; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px; border: 1px solid #e5e7eb;">
    <h2 style="color: #4f46e5; margin-top: 0;">AI Interview Invitation</h2>
    <p>Dear <strong>{candidate_name}</strong>,</p>
    <p>You have been invited to complete a browser-based AI voice interview for the <strong>{job_title}</strong> role at <strong>{org_title}</strong>.</p>
    
    <div style="text-align: center; margin: 30px 0;">
      <a href="{candidate_url}" style="background-color: #4f46e5; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Start Your Interview</a>
    </div>

    <div style="background-color: #f3f4f6; padding: 16px; border-radius: 6px; font-size: 14px; margin-bottom: 24px;">
      <p style="margin: 0 0 8px 0;"><strong>Link Expiration:</strong> {expires_at_str}</p>
      <p style="margin: 0 0 8px 0;"><strong>Requirements:</strong> Modern browser (Chrome/Edge/Firefox) and working microphone.</p>
      <p style="margin: 0;"><strong>Environment:</strong> A quiet room with minimal background noise.</p>
    </div>

    <p style="font-size: 13px; color: #6b7280;">If the button above does not work, copy and paste this secure link into your browser:</p>
    <p style="font-size: 13px; color: #4f46e5; word-break: break-all;">{candidate_url}</p>

    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
    <p style="font-size: 12px; color: #9ca3af; margin: 0;">This is an automated invitation from {org_title}.</p>
  </div>
</body>
</html>
"""
