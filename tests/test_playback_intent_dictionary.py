import functools
import importlib.util
import pathlib
import sys
import types
import unittest
from datetime import datetime


jurialmunkey = types.ModuleType("jurialmunkey")
parser = types.ModuleType("jurialmunkey.parser")
parser.try_int = lambda value: int(value or 0)
ftools = types.ModuleType("jurialmunkey.ftools")
ftools.cached_property = functools.cached_property
sys.modules.setdefault("jurialmunkey", jurialmunkey)
sys.modules.setdefault("jurialmunkey.parser", parser)
sys.modules.setdefault("jurialmunkey.ftools", ftools)
tmdbhelper = types.ModuleType("tmdbhelper")
tmdbhelper_lib = types.ModuleType("tmdbhelper.lib")
tmdbhelper_addon = types.ModuleType("tmdbhelper.lib.addon")
tmdate = types.ModuleType("tmdbhelper.lib.addon.tmdate")
tmdate.get_datetime_now = datetime.now
sys.modules.setdefault("tmdbhelper", tmdbhelper)
sys.modules.setdefault("tmdbhelper.lib", tmdbhelper_lib)
sys.modules.setdefault("tmdbhelper.lib.addon", tmdbhelper_addon)
sys.modules.setdefault("tmdbhelper.lib.addon.tmdate", tmdate)

MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "resources/tmdbhelper/lib/player/dialog/dictionary.py"
)
spec = importlib.util.spec_from_file_location("tmdbhelper_player_dictionary", MODULE_PATH)
dictionary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dictionary)


class Details:
    infolabels = {
        "title": "Episode",
        "tvshowtitle": "Show",
        "year": 2026,
        "premiered": "2026-07-16",
        "plot": "Plot",
    }
    infoproperties = {}
    unique_ids = {}
    art = {}
    cast = []


class PlaybackIntentDictionaryTests(unittest.TestCase):
    def test_movie_template_expands_playback_intent(self):
        item = dictionary.PlayerDictionary(
            "movie", 100, details=Details(),
            playback_intent_id="9d178f99-975b-43d8-a48b-928b50d302d4",
        )
        self.assertEqual(
            item.string_format_map("?intent={playback_intent_id}"),
            "?intent=9d178f99-975b-43d8-a48b-928b50d302d4",
        )

    def test_episode_template_supports_url_encoding(self):
        item = dictionary.PlayerDictionary(
            "tv", 100, season=1, episode=2, details=Details(),
            playback_intent_id="intent id/with spaces",
        )
        self.assertEqual(item["playback_intent_id_url+"], "intent+id%2Fwith+spaces")
        self.assertEqual(item["season"], 1)
        self.assertEqual(item["episode"], 2)

    def test_missing_playback_intent_expands_to_empty_string(self):
        item = dictionary.PlayerDictionary("movie", 100, details=Details())
        self.assertEqual(item["playback_intent_id"], "")


if __name__ == "__main__":
    unittest.main()
