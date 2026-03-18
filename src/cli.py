"""Command-line interface for hire-katie management tasks."""

import argparse
import logging
import sys

from .services.update_service import send_weekly_updates, send_monthly_updates
from .utils.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_send_updates(args):
    """Send progress updates to clients."""
    init_db()
    
    if args.period == "weekly":
        logger.info("Sending weekly updates...")
        sent, failed = send_weekly_updates()
        logger.info(f"Weekly updates complete: {sent} sent, {failed} failed")
    elif args.period == "monthly":
        logger.info("Sending monthly updates...")
        sent, failed = send_monthly_updates()
        logger.info(f"Monthly updates complete: {sent} sent, {failed} failed")
    else:
        logger.error(f"Unknown period: {args.period}")
        return 1
    
    return 0 if failed == 0 else 1


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="hire-katie",
        description="Hire Katie management CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # send-updates command
    updates_parser = subparsers.add_parser(
        "send-updates",
        help="Send progress updates to clients"
    )
    updates_parser.add_argument(
        "period",
        choices=["weekly", "monthly"],
        help="Update period (weekly or monthly)"
    )
    updates_parser.set_defaults(func=cmd_send_updates)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
