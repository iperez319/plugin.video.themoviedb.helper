from tmdbhelper.lib.api.request import RequestAPI
from tmdbhelper.lib.api.tmdb.api import TMDbAPI
from tmdbhelper.lib.addon.plugin import get_setting
from tmdbhelper.lib.addon.consts import CACHE_SHORT, CACHE_LONG
from tmdbhelper.lib.files.bcache import BasicCache


class EpisodeGroupsAPI(RequestAPI):
    """ Cached HTTP client for the self-hosted episode groups service.

    The service stores which TMDB episode group the user selected per show.
    Selections change rarely so the full mapping list is fetched in one call
    and cached. All reads are best-effort: any failure returns None so
    playback continues with canonical numbering.
    """

    def __init__(self, base_url=None, api_key=None):
        self.base_url = (base_url or get_setting('episodegroups_baseurl', 'str') or '').rstrip('/')
        self.api_key = api_key or get_setting('episodegroups_apikey', 'str') or ''
        super(EpisodeGroupsAPI, self).__init__(
            req_api_url=self.base_url, req_api_name='EpisodeGroupsAPI', timeout=10)
        self._error_notification = False

    @property
    def is_enabled(self):
        return bool(get_setting('episodegroups_enable') and self.base_url)

    @property
    def headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers

    @headers.setter
    def headers(self, value):
        """ Ignore base class req_api attempting to set headers """
        return

    def get_episode_groups(self):
        """ GET the full list of per-show episode group selections or None """
        response = self.get_request('EpisodeGroups', cache_days=CACHE_SHORT)
        if isinstance(response, dict):  # Tolerate a {'data': [...]} envelope
            response = response.get('data')
        if not isinstance(response, list):
            return
        return response

    def get_group_id(self, tmdb_id):
        """ Return the selected episode_group_id for a show or None """
        from jurialmunkey.parser import try_int
        tmdb_id = try_int(tmdb_id)
        for item in self.get_episode_groups() or ():
            if not isinstance(item, dict):
                continue
            if try_int(item.get('tmdb_id')) == tmdb_id:
                return item.get('episode_group_id') or None
        return None


class TMDbEpisodeGroupAPI(TMDbAPI):
    """ Cached fetch of TMDB episode group details (structure changes rarely).

    TMDbAPI is a NoCacheRequestAPI so caching is restored here with a
    dedicated cache db.
    """

    _basiccache = BasicCache
    api_name = 'TMDbEpisodeGroupAPI'

    def get_episode_group_detail(self, episode_group_id):
        """ GET tv/episode_group/{id} (language-free so all locales share one cache entry) """
        return self.get_request('tv', 'episode_group', episode_group_id, cache_days=CACHE_LONG)


def get_display_numbers(tmdb_id, season, episode):
    """ Map canonical (season, episode) to the show's episode group display numbering.

    Returns (display_season, display_episode) or None. Never raises: playback
    must fall back to canonical numbering when the service or TMDB fails.
    """
    from tmdbhelper.lib.addon.logger import kodi_log
    try:
        api = EpisodeGroupsAPI()
        if not api.is_enabled:
            return None
        group_id = api.get_group_id(tmdb_id)
        if not group_id:
            return None
        detail = TMDbEpisodeGroupAPI().get_episode_group_detail(group_id)
        if not detail:
            return None
        from jurialmunkey.parser import try_int
        from tmdbhelper.lib.api.episodegroups.mapper import map_episode_group_numbers
        return map_episode_group_numbers(detail, try_int(season), try_int(episode))
    except Exception as exc:
        kodi_log(f'EpisodeGroups: mapping failed, using canonical numbers: {exc}', 1)
        return None
