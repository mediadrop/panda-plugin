# This file is a part of MediaCore-Panda, Copyright 2011 Simple Station Inc.
#
# MediaCore is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MediaCore is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

from repoze.what.predicates import has_permission
from repoze.what.plugins.pylonshq import ActionProtector

from mediacore.lib.base import BaseController
from mediacore.lib.decorators import autocommit, expose
from mediacore.lib.helpers import redirect
from mediacore.model import Media, MediaFile, fetch_row
from mediacore.model.meta import DBSession

from mediacore_panda import add_panda_vars
from mediacore_panda.lib import PandaHelper
from mediacore_panda.lib.storage import PandaStorage

log = logging.getLogger(__name__)
admin_perms = has_permission('edit')

class MediaController(BaseController):
    @ActionProtector(admin_perms)
    @expose('panda/admin/media/panda-status-box.html')
    def panda_status(self, id, **kwargs):
        media = fetch_row(Media, id)
        result = {'media': media, 'include_javascript': False}
        result = add_panda_vars(**result)

        encoding_dicts = result['encoding_dicts']
        result['display_panda_refresh_message'] = \
            not any(encoding_dicts.get(file.id) for file in media.files)

        return result

    @ActionProtector(admin_perms)
    @expose('json')
    @autocommit
    def panda_cancel(self, file_id, encoding_id, **kwargs):
        media_file = fetch_row(MediaFile, file_id)
        storage = DBSession.query(PandaStorage).first()
        storage.panda_helper().cancel_transcode(media_file, encoding_id)
        return dict(
            success = True,
        )

    @ActionProtector(admin_perms)
    @expose('json')
    @autocommit
    def panda_retry(self, file_id, encoding_id, **kwargs):
        media_file = fetch_row(MediaFile, file_id)
        storage = DBSession.query(PandaStorage).first()
        storage.panda_helper().retry_transcode(media_file, encoding_id)
        return dict(
            success = True,
        )

    @expose()
    @autocommit
    def panda_update(self, media_id=None, file_id=None, video_id=None, **kwargs):
        if file_id:
            media_file = fetch_row(MediaFile, file_id)
            media_files = [media_file]
        elif media_id:
            media = fetch_row(Media, media_id)
            media_files = media.files

        storage = DBSession.query(PandaStorage).first()

        for media_file in media_files:
            storage.panda_helper().video_status_update(media_file, video_id)

        media_files[0].media.update_status()

        redirect(controller='/admin/media', action='edit', id=media_id)
