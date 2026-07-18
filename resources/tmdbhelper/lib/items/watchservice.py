from jurialmunkey.ftools import cached_property
from tmdbhelper.lib.addon.plugin import get_setting


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _progress_percent(progress_seconds, duration_seconds):
    """ Convert a resume position in seconds to the 0-100 percentage the read layer
    (get_infoproperties_progress) expects. Returns 0 when there is no usable resume. """
    p = progress_seconds or 0
    d = duration_seconds or 0
    if p <= 0 or d <= 0:
        return 0
    return min(100, int(p * 100 / d))


class WatchServicePlayData():
    """ Watch-state provider backed by the self-hosted watch-service.

    Mirrors the TraktPlayData seam so the container can treat providers uniformly,
    but does its work in sync_items(items) — after the directory's items (and thus
    their TMDb ids) are known — because it fetches watched/resume state scoped to
    exactly those ids in one batch call. The fetched state is staged into the shared
    ItemDetails simplecache columns (the same rows the itemmeta factories read), so
    the entire read path is reused unchanged. watch-service remains the source of
    truth; these rows are a per-build read-through cache.
    """

    def __init__(self, watchedindicators=False, syncallitems=False):
        self._watchedindicators = watchedindicators
        self._syncallitems = syncallitems

    @property
    def is_enabled(self):
        return bool(self._watchedindicators and self.api.is_authorized)

    def is_sync(func):
        def wrapper(self, *args, **kwargs):
            if not self.is_enabled:
                return
            return func(self, *args, **kwargs)
        return wrapper

    @cached_property
    def api(self):
        from tmdbhelper.lib.api.watchservice.api import WatchServiceAPI
        return WatchServiceAPI()

    @cached_property
    def database(self):
        from tmdbhelper.lib.items.database.database import ItemDetailsDatabase
        return ItemDetailsDatabase()

    # The container calls pre_sync_start/pre_sync_join on the Trakt provider before/
    # after fetching items; this provider needs the item ids first, so those are
    # no-ops and the real work happens in sync_items (called before build_items).
    def pre_sync_start(self, **kwargs):
        return

    def pre_sync_join(self):
        return

    @staticmethod
    def _item_ref(item):
        """ Resolve (kind, show_id, movie_id, season, episode) from a raw item dict,
        replicating ListItemDetails' tmdb id/type resolution. Returns None for items
        that carry no watched state (persons, sets, next-page markers, unidentifiable). """
        if not isinstance(item, dict) or 'next_page' in item:
            return
        infolabels = item.get('infolabels') or {}
        unique_ids = item.get('unique_ids') or {}
        mediatype = infolabels.get('mediatype')

        if mediatype == 'movie':
            movie_id = _to_int(unique_ids.get('tmdb'))
            return ('movie', None, movie_id, None, None) if movie_id else None
        if mediatype == 'tvshow':
            show_id = _to_int(unique_ids.get('tmdb') or unique_ids.get('tvshow.tmdb'))
            return ('tvshow', show_id, None, None, None) if show_id else None
        if mediatype == 'season':
            show_id = _to_int(unique_ids.get('tvshow.tmdb'))
            season = _to_int(infolabels.get('season')) or 0
            return ('season', show_id, None, season, None) if show_id else None
        if mediatype == 'episode':
            show_id = _to_int(unique_ids.get('tvshow.tmdb'))
            if not show_id:
                return
            season = _to_int(infolabels.get('season')) or 0
            episode = _to_int(infolabels.get('episode')) or 0
            return ('episode', show_id, None, season, episode)
        return

    @is_sync
    def sync_items(self, items, forced=False):
        refs = [r for r in (self._item_ref(i) for i in (items or [])) if r]
        if not refs:
            return
        show_ids = {r[1] for r in refs if r[1] is not None}
        movie_ids = {r[2] for r in refs if r[2] is not None}

        # On-demand mode: only fetch for single-title builds (detail view or one
        # show's seasons/episodes) unless the directory forces a sync.
        if not self._syncallitems and not forced and len(show_ids) + len(movie_ids) > 1:
            return
        
        data = self.api.get_watched_batch(show_ids, movie_ids)
        if not data:
            return

        # Index the response for O(1) per-item lookup while walking the directory.
        shows = {}
        for show in data.get('shows') or []:
            show_id = _to_int(show.get('showId'))
            if show_id is None:
                continue
            seasons = {
                s.get('seasonNumber'): s
                for s in (show.get('seasons') or [])
            }
            episodes = {
                (e.get('seasonNumber'), e.get('episodeNumber')): e
                for e in (show.get('episodes') or [])
            }
            shows[show_id] = {'show': show, 'seasons': seasons, 'episodes': episodes}
        movies = {
            _to_int(m.get('movieId')): m
            for m in (data.get('movies') or [])
            if _to_int(m.get('movieId')) is not None
        }

        # Build column data grouped by simplecache column set (values align to `keys`).
        watched_counts = {}   # keys: watched_episodes, aired_episodes, last_watched_at
        plays = {}            # keys: plays
        playback = {}         # keys: playback_progress

        for kind, show_id, movie_id, season, episode in refs:
            if kind == 'tvshow':
                show = shows.get(show_id)
                if show is None:
                    continue
                s = show['show']
                watched_counts[f'tv.{show_id}'] = (
                    s.get('completed') or 0, s.get('aired') or 0, s.get('lastWatchedAt'))
            elif kind == 'season':
                show = shows.get(show_id)
                if show is None:
                    continue
                sc = show['seasons'].get(season) or {}
                watched_counts[f'tv.{show_id}.{season}'] = (
                    sc.get('watched') or 0, sc.get('aired') or 0, None)
            elif kind == 'episode':
                show = shows.get(show_id)
                ep = show['episodes'].get((season, episode)) if show else None
                item_id = f'tv.{show_id}.{season}.{episode}'
                watched = bool(ep and ep.get('watched'))
                plays[item_id] = (1 if watched else 0, )
                playback[item_id] = (
                    _progress_percent(ep.get('progressSeconds'), ep.get('durationSeconds')) if ep else 0, )
            elif kind == 'movie':
                m = movies.get(movie_id)
                item_id = f'movie.{movie_id}'
                watched = bool(m and m.get('watched'))
                plays[item_id] = (1 if watched else 0, )
                playback[item_id] = (
                    _progress_percent(m.get('progressSeconds'), m.get('durationSeconds')) if m else 0, )

        # `update_if_null` is SET col = ifnull(?, col), so a non-null value overwrites
        # and None preserves. Every visible item is written with explicit values
        # (0 for unwatched / no-resume), so stale state is cleared without a separate
        # del_column_values pass — the batch already seeds an entry per requested id.
        if watched_counts:
            self.database.set_many_values(
                keys=('watched_episodes', 'aired_episodes', 'last_watched_at'), data=watched_counts)
        if plays:
            self.database.set_many_values(keys=('plays', ), data=plays)
        if playback:
            self.database.set_many_values(keys=('playback_progress', ), data=playback)
