#!/bin/bash
# Autopilot Cron Setup — Install cron job every 10 minutes

set -e

CRON_SPEC="*/10 * * * * /config/.openclaw/workspace/ha-copilot-repo/scripts/autopilot_runner.py >> /config/.openclaw/workspace/ha-copilot-repo/autopilot.log 2>&1"
CRON_FILE="/config/.openclaw/workspace/ha-copilot-repo/autopilot.cron"

echo "Creating cron job every 10 minutes..."
echo "$CRON_SPEC" > "$CRON_FILE"
crontab "$CRON_FILE"
echo "Cron job installed:"
crontab -l

echo ""
echo "To verify: crontab -l"
echo "To remove: crontab -r"
