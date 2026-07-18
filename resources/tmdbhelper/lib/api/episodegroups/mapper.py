"""Pure mapping helpers for TMDB episode groups. No Kodi imports so it can be tested standalone."""


def map_episode_group_numbers(group_detail, season, episode):
    """ Map canonical TMDB (season, episode) to the group's display numbering.

    Mirrors the infuse-jellyfin-mock semantics: display season is the group's
    order and display episode is the episode's order within the group plus one.
    Returns (display_season, display_episode) or None if the episode is not in
    the group or the detail is malformed. Group/episode `order` can be 0 so
    only explicit None checks are valid here.
    """
    try:
        groups = group_detail['groups']
    except (KeyError, TypeError):
        return None
    for group in groups or ():
        if not isinstance(group, dict):
            continue
        for ep in group.get('episodes') or ():
            if not isinstance(ep, dict):
                continue
            if ep.get('season_number') != season or ep.get('episode_number') != episode:
                continue
            if group.get('order') is None or ep.get('order') is None:
                return None
            return (group['order'], ep['order'] + 1)
    return None
