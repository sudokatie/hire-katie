"""Email sending via himalaya CLI."""

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Email:
    """Represents an email from the inbox."""
    id: str
    from_addr: str
    subject: str
    date: str
    is_unread: bool


def render_template(
    template_name: str,
    variables: dict,
    templates_dir: str = "src/templates/email"
) -> tuple[str, str]:
    """Render an email template with variables.
    
    Template format:
        Subject: Your subject line
        
        Body content here with {variable} placeholders.
    
    Args:
        template_name: Template filename without extension
        variables: Dict of variable names to values
        templates_dir: Directory containing templates
    
    Returns:
        Tuple of (subject, body)
    
    Raises:
        FileNotFoundError: If template not found
    """
    template_path = Path(templates_dir) / f"{template_name}.txt"
    content = template_path.read_text()
    
    # Replace variables
    for key, value in variables.items():
        content = content.replace(f"{{{key}}}", str(value))
    
    # Extract subject from first line
    lines = content.split('\n')
    subject = ""
    body_start = 0
    
    for i, line in enumerate(lines):
        if line.startswith('Subject:'):
            subject = line[8:].strip()
            body_start = i + 1
            break
    
    # Skip blank lines after subject
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    
    body = '\n'.join(lines[body_start:])
    return subject, body


def send_email(
    to: str,
    subject: str,
    body: str,
    from_name: str = "Katie",
    from_addr: str = "blackabee@gmail.com"
) -> bool:
    """Send an email via himalaya CLI.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body
        from_name: Sender name
        from_addr: Sender email address
    
    Returns:
        True if sent successfully, False otherwise
    """
    mml_content = f"""From: {from_name} <{from_addr}>
To: {to}
Subject: {subject}

{body}
"""
    
    try:
        result = subprocess.run(
            ['himalaya', 'template', 'send'],
            input=mml_content,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"himalaya send failed: {result.stderr}")
            return False
        
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except subprocess.TimeoutExpired:
        logger.error("himalaya send timed out")
        return False
    except FileNotFoundError:
        logger.error("himalaya CLI not found")
        return False


def send_template(
    to: str,
    template_name: str,
    variables: dict,
    from_name: str = "Katie",
    from_addr: str = "blackabee@gmail.com",
    templates_dir: str = "src/templates/email"
) -> bool:
    """Render a template and send as email.
    
    Args:
        to: Recipient email address
        template_name: Template filename without extension
        variables: Template variables
        from_name: Sender name
        from_addr: Sender email address
        templates_dir: Templates directory
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        subject, body = render_template(template_name, variables, templates_dir)
        return send_email(to, subject, body, from_name, from_addr)
    except FileNotFoundError as e:
        logger.error(f"Template not found: {e}")
        return False


def check_inbox(page_size: int = 50) -> list[Email]:
    """List emails from inbox.
    
    Args:
        page_size: Number of emails to fetch
    
    Returns:
        List of Email objects
    """
    try:
        result = subprocess.run(
            ['himalaya', 'envelope', 'list', '--page-size', str(page_size)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"himalaya list failed: {result.stderr}")
            return []
        
        return parse_envelope_list(result.stdout)
    except subprocess.TimeoutExpired:
        logger.error("himalaya list timed out")
        return []
    except FileNotFoundError:
        logger.error("himalaya CLI not found")
        return []


def parse_envelope_list(output: str) -> list[Email]:
    """Parse himalaya envelope list output.
    
    Output format varies, but generally:
    *123  2024-01-26 from@email.com  Subject here
    
    Args:
        output: Raw output from himalaya
    
    Returns:
        List of Email objects
    """
    emails = []
    lines = output.strip().split('\n')
    
    for line in lines:
        # Look for lines starting with optional * (unread) and ID
        match = re.match(r'^\s*(\*?)(\d+)\s+(.+?)\s{2,}(.+?)\s{2,}(.+)$', line)
        if match:
            is_unread = match.group(1) == '*'
            email_id = match.group(2)
            date = match.group(3).strip()
            from_addr = match.group(4).strip()
            subject = match.group(5).strip()
            
            emails.append(Email(
                id=email_id,
                from_addr=from_addr,
                subject=subject,
                date=date,
                is_unread=is_unread
            ))
    
    return emails


def read_email(email_id: str) -> Optional[str]:
    """Read full email content.
    
    Args:
        email_id: Email ID from envelope list
    
    Returns:
        Email content or None on error
    """
    try:
        result = subprocess.run(
            ['himalaya', 'message', 'read', email_id],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return result.stdout
        
        logger.error(f"himalaya read failed: {result.stderr}")
        return None
    except subprocess.TimeoutExpired:
        logger.error("himalaya read timed out")
        return None
    except FileNotFoundError:
        logger.error("himalaya CLI not found")
        return None


def archive_email(email_id: str) -> bool:
    """Move email to All Mail (archive).
    
    Args:
        email_id: Email ID to archive
    
    Returns:
        True if archived successfully, False otherwise
    """
    try:
        result = subprocess.run(
            ['himalaya', 'message', 'move', '[Gmail]/All Mail', email_id],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"Archived email {email_id}")
            return True
        
        logger.error(f"himalaya move failed: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("himalaya move timed out")
        return False
    except FileNotFoundError:
        logger.error("himalaya CLI not found")
        return False
