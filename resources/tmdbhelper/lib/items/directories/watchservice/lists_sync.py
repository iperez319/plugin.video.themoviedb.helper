from tmdbhelper.lib.items.directories.lists_default import ListProperties, ListDefault
from tmdbhelper.lib.items.itemlist import ItemListPagination
from tmdbhelper.lib.addon.plugin import get_setting
from jurialmunkey.ftools import cached_property
from jurialmunkey.parser import try_int


class ListWatchServiceProperties(ListProperties):

    next_page = True
    sort_by = None  # Never sort: watch-service order is authoritative
    params_def = None
    filters = None
    watchservice_api = None

    def get_service_data(self):
        """ Overridden per list: raw JSON list from the watch-service or None """
        return

    def make_items(self):
        """ Overridden per list: map raw JSON to lightweight item dicts """
        return

    @cached_property
    def service_data(self):
        if not self.watchservice_api:
            return
        return self.get_service_data()

    @cached_property
    def sync_data(self):
        if not self.service_data:
            return
        return self.make_items()

    @cached_property
    def response(self):
        if not self.sync_data:
            return
        return ItemListPagination(
            meta={'mixed': self.sync_data},  # Single flat list preserves service order
            page=self.page,
            limit=self.limit,
            params_def=self.params_def,
            filters=self.filters)

    @property
    def items(self):
        if not self.response:
            return
        return self.response.items

    @property
    def finalised_items(self):
        if not self.items:
            return
        if not self.next_page:
            return self.items
        return self.items + self.response.next_page


class ListWatchServiceNextUpProperties(ListWatchServiceProperties):
    def get_service_data(self):
        return self.watchservice_api.get_next_up()

    def make_items(self):
        return [
            {
                'id': i['show_id'],  # Episodes key off the show TMDb id
                'mediatype': 'episode',
                'title': i.get('show_title'),
                'season': i.get('season_number'),
                'episode': i.get('episode_number'),
            }
            for i in self.service_data
            if i.get('show_id') and i.get('season_number') is not None and i.get('episode_number') is not None
        ]


class ListWatchServiceContinueWatchingProperties(ListWatchServiceProperties):
    def get_service_data(self):
        return self.watchservice_api.get_continue_watching()

    def make_items(self):
        items = []
        for i in self.service_data:
            if i.get('mediaType') == 'movie' and i.get('movieId'):
                items.append({
                    'id': i['movieId'],
                    'mediatype': 'movie',
                    'title': i.get('movieTitle'),
                })
            elif i.get('mediaType') == 'episode' and i.get('showId'):
                items.append({
                    'id': i['showId'],  # Episodes key off the show TMDb id
                    'mediatype': 'episode',
                    'title': i.get('showTitle'),
                    'season': i.get('seasonNumber'),
                    'episode': i.get('episodeNumber'),
                })
        return items


class ListWatchServiceSync(ListDefault):

    list_properties_class = ListWatchServiceProperties

    def configure_list_properties(self, list_properties):
        list_properties.limit = 20 * max(get_setting('pagemulti_sync', 'int'), 1)
        list_properties.plugin_name = '{localized}'
        list_properties.watchservice_api = self.watchservice_api
        return list_properties

    def get_items(self, tmdb_type=None, page=1, **kwargs):
        self.list_properties.tmdb_type = tmdb_type or 'tv'
        self.list_properties.page = try_int(page) or 1
        return self.get_items_finalised()


class ListWatchServiceNextUp(ListWatchServiceSync):

    list_properties_class = ListWatchServiceNextUpProperties

    def configure_list_properties(self, list_properties):
        list_properties = super().configure_list_properties(list_properties)
        list_properties.localize = 32545
        list_properties.container_content = 'episodes'
        return list_properties


class ListWatchServiceContinueWatching(ListWatchServiceSync):

    list_properties_class = ListWatchServiceContinueWatchingProperties

    def configure_list_properties(self, list_properties):
        list_properties = super().configure_list_properties(list_properties)
        list_properties.localize = 32546
        list_properties.container_content = 'videos'
        return list_properties

    def get_items(self, tmdb_type=None, **kwargs):
        return super().get_items(tmdb_type='both', **kwargs)
