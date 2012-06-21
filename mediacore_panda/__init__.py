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

from mediacore.model.meta import DBSession
from mediacore.plugin import events
from mediacore.plugin.events import observes

from mediacore_panda.lib.storage import PandaStorage

log = logging.getLogger(__name__)

@observes(events.Environment.routes)
def add_routes(mapper):
    mapper.connect('/admin/plugins/panda',
        controller='panda/admin/settings',
        action='panda')
    mapper.connect('/admin/plugins/panda/save',
        controller='panda/admin/settings',
        action='panda_save')

@observes(events.Admin.MediaController.edit)
def add_panda_vars(**result):
    media = result['media']
    result['encoding_dicts'] = encoding_dicts = {}
    result['video_dicts'] = video_dicts = {}
    result['profile_names'] = {}
    result['display_panda_refresh_message'] = False

    if not media.files:
        return result

    storage = DBSession.query(PandaStorage).first()
    if not storage:
        return result

    for file in media.files:
        encoding_dicts[file.id] = \
            storage.panda_helper().get_associated_encoding_dicts(file)
        video_dicts[file.id] = \
            storage.panda_helper().get_associated_video_dicts(file)

    if video_dicts or encoding_dicts:
        result['profile_names'] = storage.panda_helper().get_profile_ids_names()

    return result
