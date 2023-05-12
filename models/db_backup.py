from odoo import models, fields, api, tools, _
import os
import datetime
import time
import shutil
import gzip
import json
import tempfile
import logging
import odoo
from odoo.exceptions import AccessDenied, UserError

log = logging.getLogger(__name__)

try:
    import paramiko
except ImportError:
    raise ImportError(
        'This module needs paramiko to automatically write backups to the FTP through SFTP. '
        'Please install paramiko on your system. (sudo pip3 install paramiko)')


class DbBackup(models.Model):
    _inherit = 'db.backup'

    odoo_type = fields.Selection([('classic', 'Classic'), ('sh', 'sh')], 'Odoo DB Type', required=True, default='classic')
    backup_type = fields.Selection([('zip', 'Zip'), ('dump', 'Dump')], 'Backup Type', required=True, default='zip', compute="_compute_backup_type", inverse="_inverse_backup_type")

    @api.depends("odoo_type")
    def _compute_backup_type(self):
        for record in self:
            record.backup_type = 'zip'

    def _inverse_backup_type(self):
        pass
    
    @api.model
    def schedule_backup(self):
        log.info("executing backup")
        conf_ids = self.search([])
        for rec in conf_ids:
            local_backup_path = rec.folder
            # get latest db.backup.log record
            latest_log = self.env['db.backup.log'].search([], order='date_created desc', limit=1)
            log.info(f"latest log: {latest_log}")
            # read latest daily backup date inside json
            json_path = os.path.join(os.getcwd(), 'backup.daily', f'{rec.name}_daily.json')
            log.info(f"reading json: {json_path}")
            copied_today_local = False
            # try to open the json file with data about the backup - if it doesn't exist, there is no backup and the functions will end
            try:
                with open (json_path) as file:
                    data = json.load(file)
                    log.info(f"json file data: {data}")
                    daily_backup_date = data['backup_datetime_utc']
                    # compare backup.daily and db.bakcup.log dates
                    log.info(f"daily backup date: {daily_backup_date}")
                    log.info(f"latest logged date: {latest_log.date_created}")
                    # if equal, backup was alraedy performed and we will skip to SFTP part
                    daily_backup_date_object = datetime.datetime.strptime(daily_backup_date, "%Y-%m-%d %H:%M:%S").date()
                    if latest_log.date_created and daily_backup_date_object == latest_log.date_created.date():
                        log.info("Local backup already made today. Skipping to SFTP check")
                        copied_today_local = True

            except FileNotFoundError:
                log.warning(f"The file {json_path} was not found. Skipping to SFTP check")
                copied_today_local = True


            if not copied_today_local:
                try:
                    if not os.path.isdir(local_backup_path):
                        log.info(f"Local backup folder({local_backup_path}) doesn't exist")
                        os.makedirs(local_backup_path)
                        log.info(f"Folder {local_backup_path} created successfully")
                except:
                    raise
                # Create name for dumpfile.
                backup_file_name = '%s_%s.%s' % (time.strftime('%Y_%m_%d_%H_%M_%S'), rec.name, rec.backup_type)
                file_path = os.path.join(local_backup_path, backup_file_name)
                log.info(f"Backup will be stored locally in {file_path}")
                try:
                    # try to backup database and write it away
                    fp = open(file_path, 'wb')
                    self._take_dump(rec.name, fp, 'db.backup', rec.odoo_type, rec.backup_type)
                    fp.close()
                except Exception as error:
                    log.info(f"Couldn't backup database {rec.name}")
                    log.info("Exact error from the exception: %s", str(error))
                    os.remove(file_path)
                    continue

                backup_log = self.env['db.backup.log'].create({
                                'name': backup_file_name,
                                'date_created': datetime.datetime.today(),
                            })
                log.info(f"backup log created: {backup_log}")

            # Check if user wants to write to SFTP or not.
            log.info(f"SFTP?: {rec.sftp_write}")
            if rec.sftp_write is True:
                copied_files = rec._sftp_write()
                if copied_files:
                    log.info(f"sftp write successfull. Copied files: {copied_files}")
                    logs_to_update = self.env['db.backup.log'].search([('name', 'in', copied_files)])
                    log.info(f"The following log records will be updated: {logs_to_update}")
                    for db_log in logs_to_update:
                        db_log.write({'date_copied': datetime.datetime.today()})
                    log.info("Logs updated successfully")

            # Remove all old files (on local server) in case this is configured..
            if rec.autoremove:
                rec._autoremove()

        log.info(f"Backup successful")
    

    def _take_dump(self, db_name, stream, model, odoo_type, backup_format='zip'):
        log.info(f"Creating local backup for odoo type: {odoo_type}")
        if odoo_type == 'classic':
            return super(DbBackup, self)._take_dump()

        cron_user_id = self.env.ref('auto_backup.backup_scheduler').user_id.id
        if self._name != 'db.backup' or cron_user_id != self.env.user.id:
            log.error('Unauthorized database operation. Backups should only be available from the cron job.')
            raise AccessDenied()

        log.info('Backup DB: %s format %s', db_name, backup_format)

        # cmd = ['pg_dump', '--no-owner']
        # cmd.append(db_name)

        if backup_format == 'zip':
            with tempfile.TemporaryDirectory() as dump_dir:
                # filestore = odoo.tools.config.filestore(db_name)
                filestore_path = os.path.join(os.getcwd(), 'backup.daily', f'{db_name}_daily', 'home', 'odoo', 'data', 'filestore', db_name)
                log.info(f"filestore path: {filestore_path}")
                # if filestore_path exists, copy contents to temporary dir
                if os.path.exists(filestore_path):
                    log.info("filestore exists")
                    shutil.copytree(filestore_path, os.path.join(dump_dir, 'filestore'))
                with open(os.path.join(dump_dir, 'manifest.json'), 'w') as fh:
                    db = odoo.sql_db.db_connect(db_name)
                    with db.cursor() as cr:
                        json.dump(self._dump_db_manifest(cr), fh, indent=4)
                # cmd.insert(-1, '--file=' + os.path.join(dump_dir, 'dump.sql'))
                # odoo.tools.exec_pg_command(*cmd)
                # copy SQL dump to temp dir
                sql_dump_path = os.path.join(os.getcwd(), 'backup.daily', f"{db_name}_daily.sql.gz")
                log.info(f"sql_dump_path: {sql_dump_path}")
                with gzip.open(sql_dump_path, 'rb') as f_in, open(os.path.join(dump_dir, 'dump.sql'), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
                log.info("copied dump.sql")
                if stream:
                    odoo.tools.osutil.zip_dir(dump_dir, stream, include_dir=False, fnct_sort=lambda file_name: file_name != 'dump.sql')
                else:
                    t=tempfile.TemporaryFile()
                    odoo.tools.osutil.zip_dir(dump_dir, t, include_dir=False, fnct_sort=lambda file_name: file_name != 'dump.sql')
                    t.seek(0)
                    return t
        else:
            message = "Dump format is currently unsupported for odoo.sh"
            log.warning(message)
            raise UserError(message)
        
    
    def _sftp_write(self):
        """Write backup files to remote server using SFTP
            :return array of copied file names
        """
        rec = self
        copied_files = []
        try:
            log.info("trying sftp write")
            # Store all values in variables
            dir = rec.folder
            path_to_write_to = rec.sftp_path
            ip_host = rec.sftp_host
            port_host = rec.sftp_port
            username_login = rec.sftp_user
            password_login = rec.sftp_password
            log.info('sftp remote path: %s', path_to_write_to)

            try:
                s = paramiko.SSHClient()
                s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                s.connect(ip_host, port_host, username_login, password_login, timeout=20)
                sftp = s.open_sftp()
                log.info("connected to remote")
            except Exception as error:
                log.critical('Error connecting to remote server! Error: %s', str(error))

            try:
                log.info(f"changing path to: {path_to_write_to}")
                sftp.chdir(path_to_write_to)
            except IOError:
                # Create directory and subdirs if they do not exist.
                current_directory = ''
                for dirElement in path_to_write_to.split('/'):
                    current_directory += dirElement + '/'
                    try:
                        sftp.chdir(current_directory)
                    except:
                        log.info('(Part of the) path didn\'t exist. Creating it now at %s',
                                        current_directory)
                        # Make directory and then navigate into it
                        sftp.mkdir(current_directory, 777)
                        sftp.chdir(current_directory)
                        pass
            sftp.chdir(path_to_write_to)
            # Loop over all files in the directory.
            for f in os.listdir(dir):
                if rec.name in f:
                    fullpath = os.path.join(dir, f)
                    if os.path.isfile(fullpath):
                        try:
                            sftp.stat(os.path.join(path_to_write_to, f))
                            log.info(
                                'File %s already exists on the remote FTP Server ------ skipped', fullpath)
                        # This means the file does not exist (remote) yet!
                        except IOError:
                            try:
                                sftp.put(fullpath, os.path.join(path_to_write_to, f))
                                log.info('Copying File % s------ success', fullpath)
                                copied_files.append(f)
                            except Exception as err:
                                log.critical(
                                    'We couldn\'t write the file to the remote server. Error: %s', str(err))

            # Navigate in to the correct folder.
            sftp.chdir(path_to_write_to)

            log.debug("Checking expired files")
            # Loop over all files in the directory from the back-ups.
            # We will check the creation date of every back-up.
            for file in sftp.listdir(path_to_write_to):
                if rec.name in file:
                    # Get the full path
                    fullpath = os.path.join(path_to_write_to, file)
                    # Get the timestamp from the file on the external server
                    timestamp = sftp.stat(fullpath).st_mtime
                    createtime = datetime.datetime.fromtimestamp(timestamp)
                    now = datetime.datetime.now()
                    delta = now - createtime
                    # If the file is older than the days_to_keep_sftp (the days to keep that the user filled in
                    # on the Odoo form it will be removed.
                    if delta.days >= rec.days_to_keep_sftp:
                        # Only delete files, no directories!
                        if ".dump" in file or '.zip' in file:
                            log.info("Delete too old file from SFTP servers: %s", file)
                            sftp.unlink(file)
                            db_log = self.env['db.backup.log'].search([('name', '=', file)])
                            if db_log:
                                db_log.write({'date_removed_remote': datetime.datetime.today()})
            # Close the SFTP session.
            sftp.close()
            s.close()
            return copied_files
        except Exception as e:
            try:
                sftp.close()
                s.close()
            except:
                pass
            log.error('Exception! We couldn\'t back up to the FTP server. Here is what we got back '
                            'instead: %s', str(e))
            # At this point the SFTP backup failed. We will now check if the user wants
            # an e-mail notification about this.
            if rec.send_mail_sftp_fail:
                try:
                    ir_mail_server = self.env['ir.mail_server'].search([], order='sequence asc', limit=1)
                    message = "Dear,\n\nThe backup for the server " + rec.host + " (IP: " + rec.sftp_host + \
                                ") failed. Please check the following details:\n\nIP address SFTP server: " + \
                                rec.sftp_host + "\nUsername: " + rec.sftp_user + \
                                "\n\nError details: " + tools.ustr(e) + \
                                "\n\nWith kind regards"
                    catch_all_domain = self.env["ir.config_parameter"].sudo().get_param("mail.catchall.domain")
                    response_mail = "auto_backup@%s" % catch_all_domain if catch_all_domain else self.env.user.partner_id.email
                    msg = ir_mail_server.build_email(response_mail, [rec.email_to_notify],
                                                        "Backup from " + rec.host + "(" + rec.sftp_host +
                                                        ") failed",
                                                        message)
                    ir_mail_server.send_email(msg)
                except Exception:
                    pass
            return copied_files

    def _autoremove(self):
        """
            Remove local backups
        """
        rec = self
        directory = rec.folder # directory storing local backups
        # Loop over all files in the directory.
        for f in os.listdir(directory):
            fullpath = os.path.join(directory, f)
            # Only delete the ones wich are from the current database
            # (Makes it possible to save different databases in the same folder)
            if rec.name in fullpath:
                timestamp = os.stat(fullpath).st_ctime
                createtime = datetime.datetime.fromtimestamp(timestamp)
                now = datetime.datetime.now()
                delta = now - createtime
                if delta.days >= rec.days_to_keep:
                    # Only delete files (which are .dump and .zip), no directories.
                    if os.path.isfile(fullpath) and (".dump" in f or '.zip' in f):
                        log.info("Delete local out-of-date file: %s", fullpath)
                        os.remove(fullpath)
                        db_log = self.env['db.backup.log'].search([('name', '=', f)])
                        if db_log:
                            db_log.write({'date_removed_local': datetime.datetime.today()})
                        else:
                            log.warning(f"A backup ({f}) has no record in db.backup.log")
