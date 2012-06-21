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

from formencode import Invalid
from tw.forms import SingleSelectField

from mediacore.forms import CheckBoxList, ListFieldSet, TextField
from mediacore.forms.admin.storage import StorageForm
from mediacore.forms.admin.settings import real_boolean_radiobuttonlist as boolean_radiobuttonlist
from mediacore.lib.helpers import merge_dicts
from mediacore.lib.i18n import N_
from mediacore.model.meta import DBSession

from mediacore_panda.lib import PandaHelper, PandaException
from mediacore_panda.lib.storage import (CLOUDFRONT_DOWNLOAD_URI,
    CLOUDFRONT_STREAMING_URI, PANDA_ACCESS_KEY, PANDA_CLOUD_ID, PANDA_PROFILES,
    PANDA_SECRET_KEY, PANDA_API_HOST, S3_BUCKET_NAME)


class ProfileCheckBoxList(CheckBoxList):
    css_classes = ['checkboxlist']
    params = ['profiles']
    template = 'panda/admin/profile_checkboxlist.html'

class PandaForm(StorageForm):
    template = 'panda/admin/storage.html'
    fields = StorageForm.fields + [
        ListFieldSet('panda', suppress_label=True, legend=N_('Panda Account Details:', domain='mediacore_panda'), children=[
            TextField('cloud_id', maxlength=255, label_text=N_('Cloud ID', domain='mediacore_panda')),
            TextField('access_key', maxlength=255, label_text=N_('Access Key', domain='mediacore_panda')),
            TextField('secret_key', maxlength=255, label_text=N_('Secret Key', domain='mediacore_panda')),
            SingleSelectField('api_host', label_text=N_('API URL', domain='mediacore_panda'),
                options=('api.pandastream.com', 'api.eu.pandastream.com')),
        ]),
        ListFieldSet('s3', suppress_label=True, legend=N_('Amazon S3 Details:', domain='mediacore_panda'), children=[
            TextField('bucket_name', maxlength=255, label_text=N_('S3 Bucket Name', domain='mediacore_panda')),
        ]),
        ListFieldSet('cloudfront',
            suppress_label=True,
            legend=N_('Amazon CloudFront Domains (e.g. a1b2c3d4e5f6.cloudfront.net):', domain='mediacore_panda'),
            help_text=N_('If you intend to use CloudFront to serve these files, please ensure that the CloudFront domains you enter below refer to this S3 bucket.', domain='mediacore_panda'),
            children=[
            TextField('streaming_uri', maxlength=255, label_text=N_('CloudFront Streaming Domain', domain='mediacore_panda')),
            TextField('download_uri', maxlength=255, label_text=N_('CloudFront Download Domain', domain='mediacore_panda')),
        ]),
        ProfileCheckBoxList('profiles', label_text=N_('Encodings to use', domain='mediacore_panda')),
    ] + StorageForm.buttons

    def display(self, value, engine, **kwargs):
        try:
            profiles = engine.panda_helper().client.get_profiles()
            cloud = engine.panda_helper().client.get_cloud()
        except PandaException:
            profiles = None
            cloud = None

        if not value:
            value = {}

        merged_value = {}
        merge_dicts(merged_value, {
            'panda': {
                'cloud_id': engine._data[PANDA_CLOUD_ID],
                'access_key': engine._data[PANDA_ACCESS_KEY],
                'secret_key': engine._data[PANDA_SECRET_KEY],
                'api_host': engine._data.get(PANDA_API_HOST),
            },
            's3': {
                'bucket_name': engine._data[S3_BUCKET_NAME],
            },
            'cloudfront': {
                'streaming_uri': engine._data[CLOUDFRONT_STREAMING_URI],
                'download_uri': engine._data[CLOUDFRONT_DOWNLOAD_URI],
            },
            'profiles': engine._data[PANDA_PROFILES],
        }, value)

        merged_kwargs = {}
        merge_dicts(merged_kwargs, {
            'cloud': cloud,
            'child_args': {
                'profiles': {'profiles': profiles},
            },
        }, kwargs)

        # kwargs are vars for the template, value is a dict of values for the form.
        return StorageForm.display(self, merged_value, engine, **merged_kwargs)

    def save_engine_params(self, engine, panda, s3, cloudfront, profiles, **kwargs):
        """Map validated field values to engine data.

        Since form widgets may be nested or named differently than the keys
        in the :attr:`mediacore.lib.storage.StorageEngine._data` dict, it is
        necessary to manually map field values to the data dictionary.

        :type engine: :class:`mediacore.lib.storage.StorageEngine` subclass
        :param engine: An instance of the storage engine implementation.
        :param \*\*kwargs: Validated and filtered form values.
        :raises formencode.Invalid: If some post-validation error is detected
            in the user input. This will trigger the same error handling
            behaviour as with the @validate decorator.

        """
        # The panda client library expects strings.
        for key in panda:
            if panda[key] is None:
                panda[key] = u''

        StorageForm.save_engine_params(self, engine, **kwargs)
        engine._data[PANDA_CLOUD_ID] = panda['cloud_id']
        engine._data[PANDA_ACCESS_KEY] = panda['access_key']
        engine._data[PANDA_SECRET_KEY] = panda['secret_key']
        engine._data[PANDA_API_HOST] = panda['api_host']
        engine._data[PANDA_PROFILES] = profiles
        engine._data[S3_BUCKET_NAME] = s3['bucket_name']
        engine._data[CLOUDFRONT_STREAMING_URI] = cloudfront['streaming_uri']
        engine._data[CLOUDFRONT_DOWNLOAD_URI] = cloudfront['download_uri']

        engine.panda_helper.cache.clear()
        try:
            engine.panda_helper().client.get_cloud()
        except PandaException, e:
            DBSession.rollback()
            # TODO: Display this error to the user.
            raise Invalid(str(e), None, None)
