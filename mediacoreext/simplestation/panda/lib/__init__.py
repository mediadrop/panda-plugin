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
import os
import simplejson
import urllib
from pprint import pformat
from socket import gaierror

import panda
from pylons import request

from mediacore.lib.helpers import download_uri
from mediacore.lib.storage import add_new_media_file
from mediacore.model.meta import DBSession
from mediacore.model.media import MediaFilesMeta

log = logging.getLogger(__name__)

# Monkeypatch panda.urlescape as per http://github.com/newbamboo/panda_client_python/commit/43e9d613bfe34ae09f2815bf026e5a5f5f0abd0a
def urlescape(s):
    s = unicode(s)
    return urllib.quote(s).replace("%7E", "~").replace(' ', '%20').replace('/', '%2F')
panda.urlescape = urlescape

PUT = 'PUT'
POST = 'POST'
DELETE = 'DELETE'
GET = 'GET'

META_VIDEO_PREFIX = u"panda_video_"
PANDA_URL_PREFIX = "panda:"
TYPES = {
    'video': "video_id",
    'encoding': "encoding_id",
    'file': "file_name",
    'url': "url",
}

# TODO: Use these lists to verify that all received data has a valid structure.
cloud_keys = [
    'id', 'created_at', 'updated_at', # Common
    'name', 's3_private_access', 's3_videos_bucket', # Cloud-specific
]
profile_keys = [
    'id', 'extname', 'created_at', 'updated_at', 'height', 'width', # Common
    'title', 'name', 'preset_name', # Profile-specific
]
video_keys = [
    'id', 'extname', 'created_at', 'updated_at', 'height', 'width', # Common
    'file_size', 'status', # Video/Encoding specific
    'source_url', 'original_filename', 'audio_codec', 'video_codec', 'duration', 'fps', # Video Specific
]
encoding_keys = [
    'id', 'extname', 'created_at', 'updated_at', 'height', 'width', # Common
    'file_size', 'status', # Video/Encoding Specific
    'encoding_progress', 'encoding_time', 'started_encoding_at', 'profile_id', 'video_id', # Encoding Specific
]

class PandaException(Exception):
    pass

def log_request(request_url, method, query_string_data, body_data, response_data):
    log.debug("Sending Panda a %s request: %s from %s", method, request_url, request.url)
    if query_string_data:
        log.debug("Query String Data: %s", pformat(query_string_data))
    if body_data:
        log.debug("Request Body Data: %s", pformat(body_data))
    log.debug("Received response: %s", pformat(response_data))

class PandaClient(object):
    def __init__(self, cloud_id, access_key, secret_key, api_host=None):
        if api_host:
            api_host = api_host.encode('utf-8')
        else:
            api_host = 'api.pandastream.com'
        self.conn = panda.Panda(
            cloud_id.encode('utf-8'),
            access_key.encode('utf-8'),
            secret_key.encode('utf-8'),
            api_host=api_host,
        )
        self.json_cache = {}

    def _get_json(self, url, query_string_data={}):
        # This function is memoized with a custom hashing algorithm for its arguments.
        hash_tuple = url, frozenset(query_string_data.iteritems())
        if hash_tuple in self.json_cache:
            return self.json_cache[hash_tuple]

        try:
            json = self.conn.get(request_path=url, params=query_string_data)
        except gaierror, e:
            # Catch socket errors and re-raise them as Panda errors.
            raise PandaException(e)

        obj = simplejson.loads(json)
        log_request(url, GET, query_string_data, None, obj)
        if 'error' in obj:
            raise PandaException(obj['error'], obj['message'])

        self.json_cache[hash_tuple] = obj
        return obj

    def _post_json(self, url, post_data={}):
        json = self.conn.post(request_path=url, params=post_data)
        obj = simplejson.loads(json)
        log_request(url, POST, None, post_data, obj)
        if 'error' in obj:
            raise PandaException(obj['error'], obj['message'])
        return obj

    def _put_json(self, url, put_data={}):
        json = self.conn.put(request_path=url, params=put_data)
        obj = simplejson.loads(json)
        log_request(url, PUT, None, put_data, obj)
        if 'error' in obj:
            raise PandaException(obj['error'], obj['message'])
        return obj

    def _delete_json(self, url, query_string_data={}):
        json = self.conn.delete(request_path=url, params=query_string_data)
        obj = simplejson.loads(json)
        log_request(url, DELETE, query_string_data, None, obj)
        if 'error' in obj:
            raise PandaException(obj['error'], obj['message'])
        return obj

    def get_cloud(self):
        """Get the data for the currently selected Panda cloud."""
        url = '/clouds/%s.json' % self.conn.cloud_id
        return self._get_json(url)

    def get_presets(self):
        """Get the configuration options for the existing encoding presets in this cloud."""
        url = '/presets.json'
        return self._get_json(url)

    def get_videos(self, status=None):
        """List all videos, filtered by status.

        :param status: Filter by status. One of 'success', 'fail', 'processing'.
        :type status: str

        :rtype: list of dicts
        """
        data = {}
        if status in ('success', 'fail', 'processing'):
            data['status'] = status
        return self._get_json('/videos.json', data)

    def get_encodings(self, status=None, profile_id=None, profile_name=None, video_id=None):
        """List all encoded instances of all videos, filtered by whatever critera are provided.

        :param status: Filter by status. One of 'success', 'fail', 'processing'.
        :type status: str

        :param profile_id: filter by profile_id
        :type profile_id: str

        :param profile_name: filter by profile_name
        :type profile_name: str

        :param video_id: filter by video_id
        :type video_id: str

        :rtype: list of dicts
        """
        data = {}
        if status in ('success', 'fail', 'processing'):
            data['status'] = status
        if profile_id:
            data['profile_id'] = profile_id
        if profile_name:
            data['profile_name'] = profile_name
        if video_id:
            data['video_id'] = video_id
        return self._get_json('/encodings.json', data)

    def get_profiles(self):
        """List all encoding profiles.

        :rtype: list of dicts
        """
        return self._get_json('/profiles.json')

    def get_video(self, video_id):
        """Get the details for a single video.

        :param video_id: The ID string of the video.
        :type video_id: str

        :rtype: dict
        """
        url = '/videos/%s.json' % video_id
        return self._get_json(url)

    def get_encoding(self, encoding_id):
        """Get the details for a single encoding of a video.

        :param encoding_id: The ID string of the encoding instance.
        :type encoding_id: str

        :rtype: dict
        """
        url = '/encodings/%s.json' % encoding_id
        return self._get_json(url)

    def get_profile(self, profile_id):
        """Get the details for a single encoding profile.

        :param profile_id: The ID string of the profile.
        :type profile_id: str

        :rtype: dict
        """
        url = '/profiles/%s.json' % profile_id
        return self._get_json(url)

    def add_profile(self, title, extname, width, height, command, name=None):
        """Add a profile using the settings provided.

        :param title: Human-readable name (e.g. "MP4 (H.264) Hi")
        :type title: str

        :param name: Machine-readable name (e.g. "h264.hi")
        :type name: str

        :param extname: file extension (including preceding .)
        :type extname: str

        :param width: Width of the encoded video
        :type width: int

        :param height: Height of the encoded video
        :type height: int

        :param command: The command to run the transcoding job.
                        (e.g. "ffmpeg -i $input_file$ -acodec libfaac -ab 128k -vcodec libx264 -vpre normal $resolution_and_padding$ -y $output_file$")
                        See http://www.pandastream.com/docs/encoding_profiles
        :type command: str
        """
        data = dict(
            title = title,
            extname = extname,
            width = width,
            height = height,
            command = command,
            name = name
        )
        if not name:
            data.pop('name')
        return self._post_json('/profiles.json', data)

    def add_profile_from_preset(self, preset_name, name=None, width=None, height=None):
        """Add a profile based on the provided preset, extending with the settings provided.

        :param preset_name: The name of the preset that will provide the basis for this encoding.
        :type preset_name: str

        :param name: Machine-readable name (e.g. "h264.hi")
        :type name: str

        :param width: Width of the encoded video
        :type width: int

        :param height: Height of the encoded video
        :type height: int
        """
        data = dict(
            preset_name = preset_name,
            name = name,
            width = width,
            height = height
        )
        for x in data:
            if data[x] == None:
                data.pop(x)
        return self._post_json('/profiles.json', data)

    def delete_encoding(self, encoding_id):
        """Delete the reference to a particular encoding from the Panda servers.

        :param encoding_id: The ID string of the encoding instance.
        :type encoding_id: str

        :returns: boolean success
        :rtype: True or False
        """
        url = '/encodings/%s.json' % encoding_id
        return self._delete_json(url)['deleted']

    def delete_video(self, video_id):
        """Delete the reference to a particular video from the Panda servers.

        :param video_id: The ID string of the video.
        :type video_id: str

        :returns: boolean success
        :rtype: True or False
        """
        url = '/videos/%s.json' % video_id
        return self._delete_json(url)['deleted']

    def delete_profile(self, profile_id):
        """Delete a particular profile from the Panda servers.

        :param profile_id: The ID string of the profile.
        :type profile_id: str

        :returns: boolean success
        :rtype: True or False
        """
        url = '/profiles/%s.json' % profile_id
        return self._delete_json(url)['deleted']

    def transcode_file(self, file_or_source_url, profile_ids, state_update_url=None):
        """Upload or mark a video file for transcoding.

        :param file_or_source_url: A file object or url to transfer to Panda
        :type file_or_source_url: A file-like object or str

        :param profile_ids: List of profile IDs to encode the video with.
        :type profile_ids: list of str

        :param state_update_url: URL for Panda to send a notification to when
                                 encoding is complete. See docs for details
                                 http://www.pandastream.com/docs/api
        :type state_update_url: str

        :returns: a dict representing the newly created video object
        :rtype: dict
        """
        if not profile_ids:
            raise Exception('Must provide at least one profile ID.')

        if not isinstance(file_or_source_url, basestring):
            raise Exception('File-like objects are not currently supported.')

        data = {
            'source_url': file_or_source_url,
            'profiles': ','.join(profile_ids),
        }
        if state_update_url:
            data['state_update_url'] = state_update_url
        return self._post_json('/videos.json', data)

    def add_transcode_profile(self, video_id, profile_id):
        """Add a transcode profile to an existing Panda video.

        :param video_id: The ID string of the video.
        :type video_id: str

        :param profile_id: The ID string of the profile.
        :type profile_id: str

        :returns: a dict representing the newly created encoding object
        :rtype: dict
        """
        data = {
            'video_id': video_id,
            'profile_id': profile_id,
        }
        return self._post_json('/encodings.json', data)


class PandaHelper(object):
    def __init__(self, cloud_id, access_key, secret_key, api_host=None):
        self.client = PandaClient(cloud_id, access_key, secret_key,
                                  api_host=api_host)

    def profile_names_to_ids(self, names):
        profiles = self.client.get_profiles()
        ids = []
        for p in profiles:
            if p['name'] in names:
                ids.append(p['id'])
        return ids

    def profile_ids_to_names(self, ids):
        profiles = self.client.get_profiles()
        names = []
        for p in profiles:
            if p['id'] in ids and p['name'] not in names:
                names.append(p['name'])
        return names

    def get_profile_ids_names(self):
        profiles = self.client.get_profiles()
        out = {}
        for profile in profiles:
            out[profile['id']] = profile['name']
        return out

    def associate_video_id(self, media_file, video_id, state=None):
        # Create a meta_key for this MediaCore::MediaFile -> Panda::Video pairing.
        # This is sort of a perversion of the meta table, but hey, it works.
        meta_key = u"%s%s" % (META_VIDEO_PREFIX, video_id)
        media_file.meta[meta_key] = state

    def disassociate_video_id(self, media_file, video_id):
        # Create a meta_key for this MediaCore::MediaFile -> Panda::Video pairing.
        # This is sort of a perversion of the meta table, but hey, it works.
        meta_key = u"%s%s" % (META_VIDEO_PREFIX, video_id)
        mfm = DBSession.query(MediaFilesMeta)\
                .filter(MediaFilesMeta.media_files_id==media_file.id)\
                .filter(MediaFilesMeta.key==meta_key)
        for x in mfm:
            DBSession.delete(x)

    def list_associated_video_ids(self, media_file):
        # This method returns a list, for futureproofing and testing, but the
        # current logic basically ensures that the list will have at most one element.
        ids = []
        offset = len(META_VIDEO_PREFIX)
        for key, value in media_file.meta.iteritems():
            if key.startswith(META_VIDEO_PREFIX):
                ids.append(key[offset:])
        return ids

    def get_associated_video_dicts(self, media_file):
        ids = self.list_associated_video_ids(media_file)
        video_dicts = {}
        for id in ids:
            video = self.client.get_video(id)
            video_dicts[video['id']] = video
        return video_dicts

    def get_associated_encoding_dicts(self, media_file):
        ids = self.list_associated_video_ids(media_file)
        encoding_dicts = {}
        for id in ids:
            v_encodings = self.client.get_encodings(video_id=id)
            for encoding in v_encodings:
                encoding_dicts[encoding['id']] = encoding
        return encoding_dicts

    def get_all_associated_encoding_dicts(self, media_files):
        encoding_dicts = {}
        for file in media_files:
            dicts = self.get_associated_encoding_dicts(file)
            if dicts:
                encoding_dicts[file.id] = dicts
        return encoding_dicts

    def get_all_associated_video_dicts(self, media_files):
        video_dicts = {}
        for file in media_files:
            dicts = self.get_associated_video_dicts(file)
            if dicts:
                video_dicts[file.id] = dicts
        return video_dicts

    def cancel_transcode(self, media_file, encoding_id):
        video_ids = self.list_associated_video_ids(media_file)

        # Ensure that the encoding to retry belongs to the given media file.
        e = self.client.get_encoding(encoding_id)
        if e['video_id'] not in video_ids:
            raise PandaException('Specified encoding is not associated with the specified media file. Cannot cancel job.', encoding_id, media_file)
        self.client.delete_encoding(encoding_id)

    def retry_transcode(self, media_file, encoding_id):
        # Ensure that the encoding to retry belongs to the given media file.
        e = self.client.get_encoding(encoding_id)
        video_ids = self.list_associated_video_ids(media_file)
        if e['video_id'] not in video_ids:
            raise PandaException('Specified encoding is not associated with the specified media file. Cannot retry.', encoding_id, media_file)

        # Upon successful deletion of the old encoding object, retry!
        if self.client.delete_encoding(encoding_id):
            self.client.add_transcode_profile(e['video_id'], e['profile_id'])
        else:
            raise PandaException('Could not delete specified encoding.', encoding_id)

    def transcode_media_file(self, media_file, profile_ids, state_update_url=None):
        uri = download_uri(media_file)
        if not uri:
            raise PandaException('Cannot transcode because no download URL exists.')
        transcode_details = self.client.transcode_file(str(uri), profile_ids, state_update_url)
        self.associate_video_id(media_file, transcode_details['id'])

    def video_status_update(self, media_file, video_id=None):
        # If no ID is specified, update all associated videos!
        if video_id is None:
            video_ids = self.list_associated_video_ids(media_file)
            for video_id in video_ids:
                self.video_status_update(media_file, video_id)
            return

        v = self.client.get_video(video_id)
        encodings = self.client.get_encodings(video_id=video_id)

        # Only proceed if the video has completed all encoding steps successfully.
        if any(e['status'] != 'success' for e in encodings):
            return

        profiles = self.get_profile_ids_names()

        # For each successful encoding (and the original file), create a new MediaFile
        display_name, orig_ext = os.path.splitext(media_file.display_name)
        v['display_name'] = "(%s) %s%s" % ('original', display_name, v['extname'])
        url = PANDA_URL_PREFIX + simplejson.dumps(v)
        new_mf = add_new_media_file(media_file.media, url=url)

        for e in encodings:
            # Panda reports multi-bitrate http streaming encodings as .ts file
            # but the associated playlist is the only thing ipods, etc, can read.
            if e['extname'] == '.ts':
                e['extname'] = '.m3u8'

            e['display_name'] = "(%s) %s%s" % (profiles[e['profile_id']].replace('_', ' '), display_name, e['extname'])
            url = PANDA_URL_PREFIX + simplejson.dumps(e)
            new_mf = add_new_media_file(media_file.media, url=url)

        self.disassociate_video_id(media_file, v['id'])
        # TODO: Now delete the exisitng media_file?
