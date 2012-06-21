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
import simplejson

from pylons import request

from mediacore.lib.decorators import autocommit, memoize
from mediacore.lib.helpers import download_uri, url_for
from mediacore.lib.storage import FileStorageEngine, LocalFileStorage, StorageURI, UnsuitableEngineError, CannotTranscode
from mediacore.lib.filetypes import guess_container_format, guess_media_type, VIDEO
from mediacore.model.meta import DBSession

from mediacore_panda.lib import PANDA_URL_PREFIX, TYPES

PANDA_ACCESS_KEY = u'panda_access_key'
PANDA_SECRET_KEY = u'panda_secret_key'
PANDA_CLOUD_ID = u'panda_cloud_id'
PANDA_PROFILES = u'panda_profiles'
PANDA_API_HOST = u'panda_api_host'
S3_BUCKET_NAME = u's3_bucket_name'
CLOUDFRONT_DOWNLOAD_URI = u'cloudfront_download_uri'
CLOUDFRONT_STREAMING_URI = u'cloudfront_streaming_uri'

from mediacore_panda.forms.admin.storage import PandaForm
from mediacore_panda.lib import PandaHelper

log = logging.getLogger(__name__)

class PandaStorage(FileStorageEngine):

    engine_type = u'PandaStorage'
    """A uniquely identifying unicode string for the StorageEngine."""

    default_name = u'Panda Transcoding & Storage'

    settings_form_class = PandaForm
    """Your :class:`mediacore.forms.Form` class for changing :attr:`_data`."""

    try_before = [LocalFileStorage]
    """Storage Engines that should :meth:`parse` after this class.

    This is a list of StorageEngine class objects which is used to
    perform a topological sort of engines. See :func:`sort_engines`
    and :func:`add_new_media_file`.
    """

    _default_data = {
        PANDA_ACCESS_KEY: u'',
        PANDA_SECRET_KEY: u'',
        PANDA_CLOUD_ID: u'',
        PANDA_API_HOST: u'',
        PANDA_PROFILES: [],
        S3_BUCKET_NAME: u'',
        CLOUDFRONT_DOWNLOAD_URI: u'',
        CLOUDFRONT_STREAMING_URI: u'',
    }

    @property
    @memoize
    def base_urls(self):
        s3_bucket = self._data[S3_BUCKET_NAME]
        cloudfront_http = self._data[CLOUDFRONT_DOWNLOAD_URI]
        cloudfront_rtmp = self._data[CLOUDFRONT_STREAMING_URI]
        # TODO: Return a dict or something easier to parse elsewhere
        urls = [('http', 'http://%s.s3.amazonaws.com/' % s3_bucket)]
        if cloudfront_http:
            urls.append(('http', 'http://%s/' % cloudfront_http.strip(' /')))
        else:
            urls.append((None, None))
        if cloudfront_rtmp:
            urls.append(('rtmp', 'rtmp://%s/cfx/st/' % cloudfront_rtmp.strip(' /')))
        else:
            urls.append((None, None))
        return urls

    @memoize
    def panda_helper(self):
        return PandaHelper(
            cloud_id = self._data[PANDA_CLOUD_ID],
            access_key = self._data[PANDA_ACCESS_KEY],
            secret_key = self._data[PANDA_SECRET_KEY],
            api_host = self._data.get(PANDA_API_HOST),
        )

    def parse(self, file=None, url=None):
        """Return metadata for the given file or raise an error.

        :type file: :class:`cgi.FieldStorage` or None
        :param file: A freshly uploaded file object.
        :type url: unicode or None
        :param url: A remote URL string.
        :rtype: dict
        :returns: Any extracted metadata.
        :raises UnsuitableEngineError: If file information cannot be parsed.

        """
        if not url or not url.startswith(PANDA_URL_PREFIX):
            raise UnsuitableEngineError()

        offset = len(PANDA_URL_PREFIX)
        # 'd' is the dict representing a Panda encoding or video
        # with an extra key: 'display_name'
        d = simplejson.loads(url[offset:])

        # MediaCore uses extensions without prepended .
        ext = d['extname'].lstrip('.').lower()

        # XXX: Panda doesn't actually populate these fields yet.
        ba = d.get('audio_bitrate', None) or 0
        bv = d.get('video_bitrate', None) or 0
        bitrate = (ba + bv) or None

        return {
            'unique_id': d['id'] + d['extname'],
            'container': guess_container_format(ext),
            'display_name': d['display_name'],
            'type': VIDEO, # only video files get panda encoded, so it's video Q.E.D.
            'height': d['height'],
            'width': d['width'],
            'size': d['file_size'],
            'bitrate': bitrate,
            'duration': d['duration'] / 1000.0,
            'thumbnail_url': "%s%s_1.jpg" % (self.base_urls[0][1], d['id']),
        }

    def transcode(self, media_file):
        """Transcode an existing MediaFile.

        The MediaFile may be stored already by another storage engine.
        New MediaFiles will be created for each transcoding generated by this
        method.

        :type media_file: :class:`~mediacore.model.media.MediaFile`
        :param media_file: The MediaFile object to transcode.
        :raises CannotTranscode: If this storage engine can't or won't transcode the file.
        :rtype: NoneType
        :returns: Nothing
        """
        if isinstance(media_file.storage, PandaStorage):
            return

        profile_names = self._data[PANDA_PROFILES]

        if not profile_names \
        or media_file.type != VIDEO \
        or not download_uri(media_file):
            raise CannotTranscode

        panda_helper = self.panda_helper()
        state_update_url = url_for(
            controller='/panda/admin/media',
            action='panda_update',
            file_id=media_file.id,
            qualified=True
        )

        # We can only tell panda to encode this video once the transaction has
        # been committed, otherwise panda get's a 404 when they try to download
        # the file from us.
        def transcode():
            try:
                panda_helper.transcode_media_file(media_file, profile_names,
                                                  state_update_url=state_update_url)
            except PandaException, e:
                log.exception(e)

        # Ideally we have the @autocommit decorator call the transcode function
        # after the transaction has been committed normally. This functionality
        # wasn't added until after the release of v0.9.0 final, so we have an
        # ugly hack to support that version.
        if hasattr(request, 'commit_callbacks'):
            # Use the autocommit decorator to save the changes to the db.
            autocommitted_transcode = autocommit(transcode)
            request.commit_callbacks.append(autocommitted_transcode)
        else:
            DBSession.commit()
            transcode()

    def get_uris(self, media_file):
        """Return a list of URIs from which the stored file can be accessed.

        :type media_file: :class:`~mediacore.model.media.MediaFile`
        :param media_file: The associated media file object.
        :rtype: list
        :returns: All :class:`StorageURI` tuples for this file.

        """
        base_urls = list(self.base_urls)

        # Skip s3 http url if cloudfront http url is available
        if base_urls[1][0]:
            base_urls = base_urls[1:]

        uris = []
        file_uri = media_file.unique_id
        for scheme, base_url in base_urls:
            if not scheme:
                continue
            uri = StorageURI(media_file, scheme, file_uri, base_url)
            uris.append(uri)
        return uris

FileStorageEngine.register(PandaStorage)
