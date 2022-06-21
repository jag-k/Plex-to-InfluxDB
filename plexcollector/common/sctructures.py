import dataclasses
from typing import Union, Optional

from plexapi.audio import Track
from plexapi.media import TranscodeSession, Media
from plexapi.video import Episode, Movie

MEDIA_TYPE = Union[Episode, Movie, Track]


@dataclasses.dataclass()
class StreamData:
    full_title: str = "Unknown"
    resolution: str = ""
    container: str = ""
    audio_codec: str = ""
    length_ms: int = 0
    grandparent_title: str = ""
    parent_title: str = ""
    parent_index: str = ""
    title: str = ""
    index: str = ""
    year: str = ""
    player_state: str = ""
    position: int = 0
    pos_percent: float = 0.0
    transcode_video: str = ""
    transcode_audio: str = ""
    transcode_summary: str = ""
    video_codec: str = ""
    video_framerate: str = ""

    def stream_processor(self, stream: MEDIA_TYPE):
        combined_video_transcodes = 0
        combined_audio_transcodes = 0

        # Don't error out on unknown stream types
        if stream.type not in MEDIA_TYPES:
            return self, combined_video_transcodes, combined_audio_transcodes

        self.position = stream.viewOffset

        self.title = stream.title

        self.full_title = stream.title
        self.grandparent_title = getattr(stream, 'grandparentTitle', '')
        if self.grandparent_title:
            self.full_title = self.grandparent_title + ' - ' + stream.title

        if stream.type in ('episode', 'track'):
            self.parent_title = getattr(stream, 'parentTitle', '')

        if stream.type == 'episode':
            self.parent_index = getattr(stream, 'parentIndex', '')

        media: Media = stream.media[0]

        self.resolution = media.videoResolution
        if stream.type == 'track':
            self.resolution = str(self.resolution) + 'Kbps'

        # Common fields
        self.audio_codec = media.audioCodec
        transcode_session: Optional[TranscodeSession] = (
            getattr(
                stream,
                'transcodeSessions',
                [None]
            ) or [None]
        )[0]

        if transcode_session is not None:
            if transcode_session.audioDecision == 'transcode':
                self.transcode_audio = "Transcoding"
                combined_audio_transcodes += 1
                self.transcode_summary += "A: Yes"
            else:
                self.transcode_audio = "DirectStream"
                self.transcode_summary += "A: No"
        else:
            self.transcode_audio = "DirectPlay"
            self.transcode_summary += "A: No"

        self.container = media.container
        self.length_ms = media.duration

        # Calculate percent of total length played
        if int(self.position) > 0 and int(self.length_ms) > 0:
            self.pos_percent = round(int(self.position) / int(self.length_ms), 4)

        # index is typically the episode number for TV, or track number for music
        self.index = getattr(stream, 'index', '')

        return self, combined_video_transcodes, combined_audio_transcodes


MEDIA_TYPES = {
    'movie': 'Movie',
    'episode': 'TV Shows',
    'track': 'Music',
}
