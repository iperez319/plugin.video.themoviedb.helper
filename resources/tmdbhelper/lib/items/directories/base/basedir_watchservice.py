from tmdbhelper.lib.items.directories.base.basedir_item import BaseDirItem


class BaseDirItemWatchServiceAuthorised(BaseDirItem):
    @property
    def enabled(self):
        from tmdbhelper.lib.addon.plugin import get_setting
        return bool(
            get_setting('watchservice_baseurl', 'str')
            and get_setting('watchservice_apikey', 'str')
            and get_setting('watchservice_userid', 'str'))


class BaseDirItemWatchServiceNextUp(BaseDirItemWatchServiceAuthorised):
    priority = 100
    label_type = 'localize'
    label_localized = 32545
    types = ('tv', )
    params = {'info': 'watchservice_nextup'}
    art_icon = 'resources/icons/trakt/inprogress.png'
    group = 32540


class BaseDirItemWatchServiceContinueWatching(BaseDirItemWatchServiceAuthorised):
    priority = 110
    label_type = 'localize'
    label_localized = 32546
    types = ('tv', 'movie', )
    params = {'info': 'watchservice_continuewatching'}
    art_icon = 'resources/icons/trakt/inprogress.png'
    group = 32540


def get_all_watchservice_class_instances():
    from tmdbhelper.lib.addon.module import get_all_module_class_objects_by_priority
    return [clobj() for clobj in get_all_module_class_objects_by_priority(__name__)]
