# auto_backup_odoosh

This is an addon for [`auto_backup`](https://github.com/Yenthe666/auto_backup) module. It adds support for odoo.sh.

`auto_backup` can't be used on odoo.sh, because you can't run `pg_dump` on odoo.sh, which is essential for making backups. This module solves this issue by grabing the backup odoo.sh creates daily, transformes it to a standard format (same that is created using the `/database/manager` tools) and then copies it to the remote location if selected. 

> :warning: **This module is still very young.** Use at your own risk.

## Features
1. odoo.sh support for creating backups and copying them to a remote location
2. Adds a model to store information about performed backups (db.backup.log)

## How to use
1. Go to: settings --> technical --> Back-ups --> Configure back-ups
2. Create a new configuration, select "sh" as odoo type and fill in the remaining data
3. To see all performed backups and when they were created (and possibly copied to remote location or removed, depending on settings), go to settings --> technical --> Back-ups --> Backup log
4. The cron job triggering backups is disabled by default. To enable, edit or trigger it manually, you must go to Scheduled Actions and find "Backup scheduler". 

The cron job should run multiple times every day - ideally every hour. Since we don't know, when exactly the ODOO.sh automation creates the backup, if you run the cron job frequently, you minimize the time when the backup is not safely stored on a remote location. 

The cron job first checks if there is a new odoo.sh backup on the odoo.sh instance. If there is, it is copied over to the remote location. So most of the time the cron job doesn't use virtually any resources. 

## Dependencies

This module depends on the module [`auto_bakcup`](https://github.com/Yenthe666/auto_backup).



