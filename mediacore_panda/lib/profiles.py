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

preset_encodings = [
    {
        'name': 'h264',
        'title': 'MP4 (H.264)',
        'extname': '.mp4',
        'width': 480,
        'command': 'ffmpeg06 -i $input_file$ -acodec libfaac -ab 128k -ar 44100 -vcodec libx264 -vpre normal -vb 500k $resolution_and_padding$ -y video_tmp_noqt.mp4\nqt-faststart video_tmp_noqt.mp4 $output_file$',
        'height': 320,
    },
    {
        'name': 'webm',
        'title': 'WebM (VP8)',
        'extname': '.webm',
        'width': 480,
        'command': 'ffmpeg06 -i $input_file$ -acodec libvorbis -ab 128k -vcodec libvpx -vpre 360p -vb 500k $resolution_and_padding$ -y $output_file$',
        'height': 320,
    },
    {
        'name': 'ogg',
        'title': 'OGG (Theora)',
        'extname': '.ogv',
        'width': 480,
        'command': 'ffmpeg2theora $input_file$ --max_size $width$x$height$ --videobitrate 500 --audiobitrate 128 -o $output_file$',
        'height': 320,
    },
    {
        'name': 'h264.hi',
        'title': 'MP4 (H.264) Hi',
        'extname': '.mp4',
        'width': 720,
        'command': 'ffmpeg06 -i $input_file$ -acodec libfaac -ab 128k -ar 44100 -vcodec libx264 -vpre hq -vb 1000k $resolution_and_padding$ -y video_tmp_noqt.mp4\nqt-faststart video_tmp_noqt.mp4 $output_file$',
        'height': 480,
    },
    {
        'name': 'webm.hi',
        'title': 'WebM (VP8) Hi',
        'extname': '.webm',
        'width': 720,
        'command': 'ffmpeg06 -i $input_file$ -acodec libvorbis -ab 128k -vcodec libvpx -vpre 720p -vb 1000k $resolution_and_padding$ -y $output_file$',
        'height': 480,
    },
    {
        'name': 'ogg.hi',
        'title': 'OGG (Theora) Hi',
        'extname': '.ogv',
        'width': 720,
        'command': 'ffmpeg2theora $input_file$ --max_size $width$x$height$ --videobitrate 1000 --audiobitrate 128 -o $output_file$',
        'height': 480,
    },
    {
        'name': 'iphone_and_ipad',
        'title': 'iPhone & iPad adaptive stream',
        'extname': '.ts',
        'width': 400,
        'command': """
ffmpeg06 -i $input_file$ -vcodec libx264 -vpre superfast -vpre baseline -acodec libfaac -ar 22050 -r 10 -vb 110k -ab 40k -g 30 -level 30 $scale_400x300_or_400x224$ -y $record_id$_110k.ts
ffmpeg06 -i $input_file$ -vcodec libx264 -vpre superfast -vpre baseline -acodec libfaac -ar 22050 -r 15 -vb 200k -ab 40k -g 45 -level 30 $scale_400x300_or_400x224$ -y $record_id$_200k.ts
ffmpeg06 -i $input_file$ -vcodec libx264 -vpre fast -vpre baseline -acodec libfaac -ar 22050 -r 29.97 -vb 400k -ab 40k -g 90 -level 30 $scale_400x300_or_400x224$ -y $output_file$
ffmpeg06 -i $input_file$ -vcodec libx264 -vpre fast -vpre baseline -acodec libfaac -ar 22050 -r 29.97 -vb 600k -ab 40k -g 90 -level 30 $scale_400x300_or_400x224$ -y $record_id$_600k.ts
ffmpeg06 -i $input_file$ -vcodec libx264 -vpre fast -vpre main -acodec libfaac -ar 22050 -r 29.97 -vb 800k -ab 40k -g 90 -level 31 $scale_640x480_or_640x360$ -y $record_id$_800k.ts
segmenter $record_id$_110k.ts 10 $record_id$_110k $record_id$_110k.m3u8  http://$bucket_name$.s3.amazonaws.com/
segmenter $record_id$_200k.ts 10 $record_id$_200k $record_id$_200k.m3u8 http://$bucket_name$.s3.amazonaws.com/
segmenter $record_id$.ts 10 $record_id$ $record_id$_400k.m3u8 http://$bucket_name$.s3.amazonaws.com/
segmenter $record_id$_600k.ts 10 $record_id$_600k $record_id$_600k.m3u8 http://$bucket_name$.s3.amazonaws.com/
segmenter $record_id$_800k.ts 10 $record_id$_800k $record_id$_800k.m3u8 http://$bucket_name$.s3.amazonaws.com/
manifester $record_id$.m3u8 http://$bucket_name$.s3.amazonaws.com/$record_id$_110k.m3u8 http://$bucket_name$.s3.amazonaws.com/$record_id$_200k.m3u8 http://$bucket_name$.s3.amazonaws.com/$record_id$_400k.m3u8 http://$bucket_name$.s3.amazonaws.com/$record_id$_600k.m3u8 http://$bucket_name$.s3.amazonaws.com/$record_id$_800k.m3u8
        """.strip(),
        'height': 300,
    }
]

web_profiles = [
    {
        'name': 'h264',
        'width': 480,
        'height': 320,
        'preset_name': 'h264'
    },
    {
        'name': 'h264.hi',
        'width': 720,
        'height': 480,
        'preset_name': 'h264.hi'
    },
    {
        'name': 'webm',
        'width': 480,
        'height': 320,
        'preset_name': 'webm'
    },
    {
        'name': 'iphone_and_ipad',
        'width': 400,
        'height': 300,
        'preset_name': 'iphone_and_ipad'
    },
]

custom_profiles = [
    {
        'name': 'h264.16x9',
        'width': 560,
        'height': 315,
        'preset_name': 'h264'
    },
    {
        'name': 'h264.hi.16x9',
        'width': 854,
        'height': 480,
        'preset_name': 'h264.hi'
    },
    {
        'name': 'webm.16x9',
        'width': 560,
        'height': 315,
        'preset_name': 'webm'
    },
]

def add_custom_profiles():
    # Add all the custom profiles to the first existing PandaStorage instance.
    from mediacore.model import DBSession
    from mediacore_panda.lib.storage import PandaStorage
    ps = DBSession.query(PandaStorage).all()[0]
    profiles = ps.panda_helper().client.get_profiles()
    pnames = [p['name'] for p in profiles]
    for x in custom_profiles:
        if x['name'] not in pnames:
            ps.panda_helper().client.add_profile_from_preset(**x)
