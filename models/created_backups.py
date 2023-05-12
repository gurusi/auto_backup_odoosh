from odoo import models, fields, api, tools, _
import logging

log = logging.getLogger(__name__)

class CreatedBackups(models.Model):
    _name = 'db.backup.log'
    _description = 'History of performed backups'

    name = fields.Char()
    date_created = fields.Datetime(string='Date created', help="when the backup was created and stored locally")
    date_copied = fields.Datetime(string='Date copied', help="when the backup was copied to remote location with sftp")
    date_removed_local = fields.Datetime(string='Date removed local', help="when the backup was automatically removed from local system. If the file was manually deleted this field will remain empty.")
    date_removed_remote = fields.Datetime(string='Date removed remote', help="when the backup was automatically removed from remote system. If the file was manually deleted this field will remain empty.")