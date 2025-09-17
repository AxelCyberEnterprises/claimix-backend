"""
Management commands for working with audit logs.
"""
from datetime import datetime, timedelta
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q

from audit.models import AuditLog


class Command(BaseCommand):
    """
    Manage audit logs from the command line.
    
    Available subcommands:
    - cleanup: Remove old audit log entries
    - stats: Show statistics about audit logs
    """
    help = 'Manage audit logs'
    
    def add_arguments(self, parser):
        """Define command-line arguments."""
        subparsers = parser.add_subparsers(dest='subcommand', required=True)
        
        # Cleanup subcommand
        cleanup_parser = subparsers.add_parser(
            'cleanup',
            help='Remove old audit log entries'
        )
        cleanup_parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Delete logs older than this many days (default: 365)'
        )
        cleanup_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting anything'
        )
        
        # Stats subcommand
        stats_parser = subparsers.add_parser(
            'stats',
            help='Show statistics about audit logs'
        )
        stats_parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Show stats for the last N days (default: 30)'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        subcommand = options['subcommand']
        
        if subcommand == 'cleanup':
            self.handle_cleanup(**options)
        elif subcommand == 'stats':
            self.handle_stats(**options)
    
    def handle_cleanup(self, days, dry_run, **kwargs):
        """Handle the cleanup subcommand."""
        cutoff_date = timezone.now() - timedelta(days=days)
        logs = AuditLog.objects.filter(timestamp__lt=cutoff_date)
        
        self.stdout.write(
            self.style.NOTICE(
                f'Found {logs.count()} log entries older than {days} days '
                f'(before {cutoff_date.strftime("%Y-%m-%d")})'
            )
        )
        
        if not logs.exists():
            self.stdout.write(self.style.SUCCESS('No logs to clean up.'))
            return
        
        if not dry_run:
            deleted_count, _ = logs.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {deleted_count} log entries.')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Dry run - no logs were deleted. ')
                + 'Use --dry-run=False to actually delete logs.'
            )
    
    def handle_stats(self, days, **kwargs):
        """Handle the stats subcommand."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get total count
        total_logs = AuditLog.objects.count()
        recent_logs = AuditLog.objects.filter(timestamp__gte=cutoff_date)
        
        # Get action counts
        action_counts = (
            AuditLog.objects
            .filter(timestamp__gte=cutoff_date)
            .values('action')
            .annotate(count=models.Count('action'))
            .order_by('-count')
        )
        
        # Get user activity
        user_activity = (
            AuditLog.objects
            .filter(timestamp__gte=cutoff_date)
            .exclude(user__isnull=True)
            .values('user__email')
            .annotate(count=models.Count('id'))
            .order_by('-count')
        )
        
        # Output the stats
        self.stdout.write(self.style.SUCCESS('Audit Log Statistics'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Time period: Last {days} days (since {cutoff_date.strftime("%Y-%m-%d")})')
        self.stdout.write(f'Total logs in system: {total_logs:,}')
        self.stdout.write(f'Logs in time period: {recent_logs.count():,}')
        
        self.stdout.write('\nTop Actions:')
        for item in action_counts[:10]:
            self.stdout.write(f'  {item["action"]}: {item["count"]:,}')
        
        self.stdout.write('\nTop Users by Activity:')
        for item in user_activity[:10]:
            self.stdout.write(f'  {item["user__email"]}: {item["count"]:,} actions')
        
        # Add some summary stats
        avg_per_day = recent_logs.count() / days if days > 0 else 0
        self.stdout.write(f'\nAverage logs per day: {avg_per_day:.1f}')
