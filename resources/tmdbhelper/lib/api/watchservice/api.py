from tmdbhelper.lib.api.request import NoCacheRequestAPI
from tmdbhelper.lib.addon.plugin import get_setting


class WatchServiceAPI(NoCacheRequestAPI):
    """ Thin HTTP client for the self-hosted watch-service.

    Reads its connection details (base URL, bearer API key, user id) from the
    addon settings. All reads are live and best-effort: any failure returns None
    so a directory still builds without watched indicators rather than erroring.
    """

    def __init__(self, base_url=None, api_key=None, user_id=None):
        self.base_url = (base_url or get_setting('watchservice_baseurl', 'str') or '').rstrip('/')
        self.api_key = api_key or get_setting('watchservice_apikey', 'str') or ''
        self.user_id = user_id or get_setting('watchservice_userid', 'str') or ''
        super(WatchServiceAPI, self).__init__(
            req_api_url=self.base_url, req_api_name='WatchServiceAPI', timeout=20)

    @property
    def is_authorized(self):
        return bool(self.base_url and self.api_key and self.user_id)

    @property
    def headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

    @headers.setter
    def headers(self, value):
        """ Ignore base class req_api attempting to set headers """
        return

    def _post_json(self, *args, postdata=None):
        from tmdbhelper.lib.files.futils import json_dumps
        request = self.get_api_request(
            self.get_request_url(*args),
            postdata=json_dumps(postdata) if postdata is not None else None,
            headers=self.headers,
            method='post')
        if not request:
            return
        try:
            return request.json()
        except ValueError:
            return

    def _get_json(self, *args):
        request = self.get_api_request(self.get_request_url(*args), headers=self.headers)
        if not request:
            return
        try:
            return request.json()
        except ValueError:
            return

    def _get_data(self, *args):
        if not self.is_authorized:
            return
        response = self._get_json(*args)
        if not response or not response.get('success'):
            return
        return response.get('data')

    def get_next_up(self):
        """ GET the next unwatched episode for each followed in-progress show or None """
        return self._get_data('users', self.user_id, 'next-up')

    def get_continue_watching(self):
        """ GET partially watched episodes/movies newest-first or None """
        return self._get_data('users', self.user_id, 'continue-watching')

    def get_watched_batch(self, show_ids, movie_ids):
        """ POST the current directory's TMDb ids and return the batch watched/resume
        state (the `data` object) or None on any failure. """
        if not self.is_authorized:
            return
        if not show_ids and not movie_ids:
            return
        response = self._post_json(
            'users', self.user_id, 'watched', 'batch',
            postdata={
                'showIds': sorted(show_ids),
                'movieIds': sorted(movie_ids),
            })
        if not response or not response.get('success'):
            return
        return response.get('data')
