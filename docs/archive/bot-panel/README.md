# Archived Bot management UI

Removed from the served panel for the user's personal Tiandixing-only server (2026-09-18).
The HTML section, JavaScript and former UI smoke workflow are retained here; they are not served.
Full pre-change source snapshot: deployment-1.3.0/bot-management-before-r17.zip (outside the repository).
The immutable BotLibrary implementation remains for transactional deployment, hash checks and rollback.
On CT270, bot-library/fixed-policy.json pins item 1573671599 and its verified content SHA. Bot mutation jobs are rejected while this policy exists; game startup rejects mismatched selection or disabled addon/Bot loading. The public console no longer accepts population commands.
