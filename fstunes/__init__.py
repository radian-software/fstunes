import argparse
import bisect
import collections
import math
import mutagen
import os
import pathlib
import random
import re
import shutil
import string
import sys

def has_duplicates(l):
    return len(l) != len(set(l))

def iter_len(iterable):
    return sum(1 for _ in iterable)

def plural(n):
    return "s" if n != 1 else ""

def pluralen(n):
    return plural(len(n))

def plurals(n):
    return n, plural(n)

def pluralens(n):
    return plurals(len(n))

def log(message, *args, **kwargs):
    print("fstunes: {}".format(message), *args, file=sys.stderr, **kwargs)

def die(message=None, *args, **kwargs):
    if message is not None:
        log(message, *args, **kwargs)
    sys.exit(1)

def are_you_sure(default, yes):
    prompt = "[Y/n]" if default else "[y/N]"
    print("Proceed? {} ".format(prompt), end="")
    if yes:
        response = "y (from command-line options)"
        print(response)
    else:
        response = input()
    if response.lower().startswith("y"):
        return True
    if response.lower().startswith("n"):
        return False
    return default

def add_yes_option(parser):
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Don't ask for confirmation")

def add_fields_option(parser):
    parser.add_argument("-f", "--fields", metavar="FIELD1,FIELD2,...",
                        help="Which metadata fields to include")

def add_match_options(parser):
    parser.add_argument("-m", "--match", metavar="FIELD=EXPR", action="append",
                        help="Filter songs")
    parser.add_argument("--match-literal", metavar="FIELD=VALUE",
                        action="append", help="Filter songs by literal match")
    parser.add_argument("--match-set", metavar="FIELD=VALUE1,VALUE2,...",
                        action="append", help="Filter songs by set membership")
    parser.add_argument("--match-range", metavar="FIELD=LOW-HIGH",
                        action="append",
                        help="Filter songs by range inclusion")
    parser.add_argument("-M", "--match-all", metavar="FIELD", action="append",
                        help="Do not filter songs")

    parser.add_argument("--set-delimiter", default=",", metavar="DELIM",
                        help="Delimiter to use for set filtering")
    parser.add_argument("--range-delimiter", default="-", metavar="DELIM",
                        help="Delimiter to use for range filtering")

SORT_OPTION_STRINGS = ("-s", "--sort")
REVERSE_OPTION_STRINGS = ("-r", "--reverse")
SHUFFLE_OPTION_STRINGS = ("-x", "--shuffle")

class SortAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string):
        if option_string in SORT_OPTION_STRINGS:
            modifier = "sort"
        elif option_string in REVERSE_OPTION_STRINGS:
            modifier = "reverse"
        elif option_string in SHUFFLE_OPTION_STRINGS:
            modifier = "shuffle"
        else:
            assert False, "unexpected modifier: {}".format(modifier)
        if not hasattr(namespace, "sort"):
            namespace.sort = []
        for value in values:
            namespace.sort.append({
                "field": value,
                "modifier": modifier,
            })

def add_sort_options(parser):
    parser.add_argument(*SORT_OPTION_STRINGS, action=SortAction,
                        help="Sort by field")
    parser.add_argument(*REVERSE_OPTION_STRINGS, action=SortAction,
                        help="Sort by field in reverse order")
    parser.add_argument(*SHUFFLE_OPTION_STRINGS, action=SortAction,
                        help="Shuffle by field")

def get_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Minimal command-line music library manager and media player."))
    subparsers = parser.add_subparsers(dest="subcommand")

    parser_import = subparsers.add_parser(
        "import", help="Add media files to library")
    parser_import.add_argument(
        "paths", nargs="+", metavar="path", help="Media file or directory")

    parser_playlist = subparsers.add_parser(
        "playlist", help="Create or delete playlists")
    subparsers_playlist = parser_playlist.add_subparsers(
        dest="subcommand_playlist")

    parser_playlist_create = subparsers_playlist.add_parser(
        "create", help="Create a playlist")
    parser_playlist_create.add_argument(
        "playlists", nargs="+", metavar="playlist",
        help="Name of playlist to create")

    parser_playlist_delete = subparsers_playlist.add_parser(
        "delete", help="Delete a playlist")
    parser_playlist_delete.add_argument(
        "playlists", nargs="+", metavar="playlist",
        help="Name of playlist to delete")
    add_yes_option(parser_playlist_delete)

    parser_insert = subparsers.add_parser(
        "insert", help="Add songs to a playlist or the queue")
    add_match_options(parser_insert)
    add_sort_options(parser_insert)
    parser_insert.add_argument(
        "-t", "--transfer", action="store_true",
        help="Also remove songs from original playlists")
    add_yes_option(parser_insert)

    group_insert_before = parser_insert.add_mutually_exclusive_group()
    group_insert_before.add_argument(
        "--before", action="store_false", help="Insert before given index")
    group_insert_before.add_argument(
        "--after", action="store_true", dest="before",
        help="Insert after given index")

    parser_insert.add_argument(
        "playlist", help="Name of playlist in which to insert")
    parser_insert.add_argument(
        "index", type=int, help="Index at which to insert")

    parser_remove = subparsers.add_parser(
        "remove", help="Remove songs from a playlist or the queue")
    add_match_options(parser_remove)
    add_yes_option(parser_remove)

    parser_edit = subparsers.add_parser(
        "edit", help="Edit song metadata")
    add_match_options(parser_edit)
    add_sort_options(parser_edit)
    add_fields_option(parser_edit)
    parser_edit.add_argument(
        "-e", "--editor", help="Shell command to run text editor")
    add_yes_option(parser_edit)

    parser_list = subparsers.add_parser(
        "list", help="List songs and associated information")
    add_match_options(parser_list)
    add_sort_options(parser_list)
    add_fields_option(parser_list)

    parser_delete = subparsers.add_parser(
        "delete", help="Delete media files from library")
    add_match_options(parser_delete)
    add_yes_option(parser_delete)

    parser_seek = subparsers.add_parser(
        "seek", help="Change place in queue and play/pause")

    group_seek_play_pause = parser_seek.add_mutually_exclusive_group()
    group_seek_play_pause.add_argument(
        "-p", "--play", action="store_true", help="Start playing")
    group_seek_play_pause.add_argument(
        "-P", "--pause", action="store_true", help="Stop playing")

    parser_seek.add_argument(
        "index", type=int, nargs="?", help="Relative index to which to seek")

    return parser

def read_mutagen_key(m, key):
    try:
        return ", ".join(m[key].text) or None
    except KeyError:
        return None

def read_metadata(filepath):
    m = mutagen.File(filepath)
    metadata = {}
    metadata["artist"] = (read_mutagen_key(m, "TPE2") or
                          read_mutagen_key(m, "TPE1"))
    metadata["album"] = read_mutagen_key(m, "TALB")
    metadata["disk"] = None
    disk_and_total = read_mutagen_key(m, "TPOS")
    if disk_and_total:
        match = re.match(r"[0-9]+", disk_and_total)
        if match:
            metadata["disk"] = int(match.group())
    metadata["track"] = None
    track_and_total = read_mutagen_key(m, "TRCK")
    if track_and_total:
        match = re.match(r"[0-9]+", track_and_total)
        if match:
            metadata["track"] = int(match.group())
    metadata["song"] = read_mutagen_key(m, "TIT2")
    metadata["extension"] = filepath.suffix
    return metadata

SAFE_CHARS = (
    string.ascii_letters + string.digits + " !\"$%&'()*+,-.[]^_`{|}~")
ESCAPE_CHAR = "#"

def escape_string(s):
    results = []
    for char in s:
        if char in SAFE_CHARS:
            results.append(char)
        else:
            results.append("{0}{1:x}{0}".format(ESCAPE_CHAR, ord(char)))
    return "".join(results)

def unescape_string(s):
    return re.sub(r"#([0-9a-f]+)#", lambda m: chr(int(m.group(1), base=16)), s)

MISSING_FIELD = "---"

def create_relpath(metadata):
    disk_str = (
        "{}-".format(metadata["disk"]) if "disk" in metadata else "")
    return pathlib.Path("{}/{}/{}{} {}{}".format(
        escape_string(metadata["artist"] or MISSING_FIELD),
        escape_string(metadata["album"] or MISSING_FIELD),
        disk_str,
        metadata.get("track", ""),
        escape_string(metadata.get("song") or MISSING_FIELD),
        metadata["extension"]))

def parse_relpath(relpath):
    match = re.fullmatch(
        r"([^/]+)/([^/]+)/(?:([0-9]+)-)?([0-9]+)? (.+)", relpath)
    artist = unescape_string(match.group(1))
    if artist == MISSING_FIELD:
        artist = None
    album = unescape_string(match.group(2))
    if album == MISSING_FIELD:
        album = None
    disk = match.group(3)
    if disk:
        disk = int(disk)
    track = match.group(4)
    if track:
        track = int(track)
    song_and_extension = match.group(5)
    song_match = re.fullmatch(r"(.+?)(\..*)", song_and_extension)
    if song_match:
        song, extension = song_match.groups()
    else:
        song = song_and_extension
    song = unescape_string(song)
    if song == MISSING_FIELD:
        song = None
    extension = match.group(6)
    return {
        "artist": artist,
        "album": album,
        "disk": disk,
        "track": track,
        "song": song,
        "extension": extension,
    }

def import_song(env, filepath):
    metadata = read_metadata(filepath)
    relpath = create_relpath(metadata)
    target = env["media"] / relpath
    if target.exists() or target.is_symlink():
        log("skipping, already exists: {} => {}"
            .format(filepath, target))
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(filepath, target)
    return True

MEDIA_EXTENSIONS = [".mp3"]

def import_music(env, paths):
    copied = 0
    already_present = 0
    skipped = 0
    for path in paths:
        path = pathlib.Path(path).resolve()
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames.sort()
            filenames.sort()
            already_reported_dir = False
            for filename in filenames:
                filepath = pathlib.Path(dirpath) / filename
                suffix = filepath.suffix
                if suffix not in MEDIA_EXTENSIONS:
                    log("skipping, extension {} not recognized: {}"
                        .format(repr(suffix), filepath))
                    skipped += 1
                    continue
                if not already_reported_dir:
                    log("importing media from directory: {}"
                        .format(filepath.parent))
                    already_reported_dir = True
                if import_song(env, filepath):
                    copied += 1
                else:
                    already_present += 1
    log(("imported {} media file{}, skipped {} "
         "already present and {} unrecognized")
        .format(*plurals(copied), already_present, skipped))

MEDIA_PLAYLIST = "media"
QUEUE_PLAYLIST = "queue"
RESERVED_PLAYLISTS = (MEDIA_PLAYLIST, QUEUE_PLAYLIST)

def create_playlists(env, playlists):
    for reserved_name in RESERVED_PLAYLISTS:
        if reserved_name in playlists:
            die("playlist name is reserved for fstunes: {}"
                .format(reserved_name))
    if has_duplicates(playlists):
        die("more than one playlist with the same name")
    paths = [env["playlists"] / escape_string(p) for p in playlists]
    should_die = False
    for playlist, path in zip(playlists, paths):
        if path.exists() or path.is_symlink():
            if path.is_dir():
                log("playlist already exists: {}".format(playlist))
            else:
                log("already exists and not a directory: {}".format(path))
            should_die = True
    if should_die:
        die()
    for path in paths:
        path.mkdir(parents=True)
    log("created {} playlist{}".format(*pluralens(playlists)))

def delete_playlists(env, playlists, yes):
    for reserved_name in RESERVED_PLAYLISTS:
        if reserved_name in playlists:
            die("playlist name is reserved for fstunes: {}"
                .format(reserved_name))
    if has_duplicates(playlists):
        die("more than one playlist with the same name")
    paths = [env["playlists"] / escape_string(p) for p in playlists]
    should_die = False
    for playlist, path in zip(playlists, paths):
        if not path.is_dir():
            if path.exists() or path.is_symlink():
                log("already exists and not a directory: {}".format(path))
            else:
                log("playlist does not exist: {}".format(playlist))
            should_die = True
    if should_die:
        die()
    total_songs = 0
    deletion_list = []
    for playlist, path in zip(playlists, paths):
        num_songs = 0
        for entry_path in path.iterdir():
            if not entry_path.is_symlink():
                continue
            try:
                int(entry_path.name)
            except ValueError:
                continue
            num_songs += 1
        total_songs += num_songs
        deletion_list.append(
            "\n  {} ({} song{})"
            .format(playlist, *plurals(num_songs)))
    log("will delete the following {} playlist{} with {} total songs:{}"
        .format(*pluralens(paths), total_songs, "".join(deletion_list)))
    if not are_you_sure(default=total_songs == 0, yes=yes):
        die()
    for path in paths:
        shutil.rmtree(path)
    log("deleted {} playlist{}".format(*pluralens(playlists)))

FSTUNES_HOME_ENV_VAR = "FSTUNES_HOME"
FSTUNES_QUEUE_LENGTH_ENV_VAR = "FSTUNES_QUEUE_LENGTH"

METADATA_FIELDS = (
    "artist",
    "album",
    "disk",
    "track",
    "song",
    "extension",
    "from",
    "index",
)

METADATA_INT_FIELDS = (
    "disk",
    "track",
    "index",
)

assert set(METADATA_INT_FIELDS).issubset(set(METADATA_FIELDS))

def split_matcher(matcher):
    return matcher.split("=", maxsplit=1)

def parse_matchers(args, default_to_media):
    matchers = collections.defaultdict(list)
    for matcher_type, unparsed_matchers in (
            ("literal", args.match_literal + args.match),
            ("set", args.match_set + args.match),
            ("range", args.match_range + args.match),
            ("all", args.match_all)):
        for unparsed_matcher in unparsed_matchers:
            field, expr = unparsed_matcher.split("=", maxsplit=1)
            if field not in METADATA_FIELDS:
                die("unsupported field: {}".format(field))
            desc = {
                "type": matcher_type,
            }
            if matcher_type == "literal":
                if field in METADATA_INT_FIELDS:
                    try:
                        expr = int(expr)
                    except ValueError:
                        die("invalid integer literal: {}".format(expr))
                desc["value"] = expr
            elif matcher_type == "set":
                expr.split(args.set_delimiter)
                try:
                    expr = list(map(int, expr))
                except ValueError:
                    die("invalid integer set: {}".format(expr))
                desc["values"] = expr
            elif matcher_type == "range":
                low, high = expr.split(args.range_delimiter, maxsplit=1)
                try:
                    low = int(low)
                    high = int(high)
                except ValueError:
                    die("invalid integer range: {}".format(expr))
                desc["low"] = low
                desc["high"] = high
            elif matcher_type == "all":
                pass
            else:
                assert False, (
                    "unexpected matcher type: {}".format(matcher_type))
            matchers[field].append(desc)
    if not matchers["from"]:
        if default_to_media:
            matchers["from"] = [{
                "type": "literal",
                "value": "media",
            }]
        else:
            die("you must select a playlist using -m from=PLAYLIST or similar")
    return matchers

def parse_sorters(args):
    sorters = []
    for sorter in args.sort:
        field = sorted["field"]
        if field not in METADATA_FIELDS:
            die("unsupported field: {}".format(field))
        sorters.append(dict(sorter))
    sorters.reverse()
    return sorters

def apply_matchers(matchers, value):
    for matcher in matchers:
        if matcher["type"] == "all":
            return True
        elif matcher["type"] == "literal":
            if value == matcher["value"]:
                return True
        elif matcher["type"] == "set":
            if value in matcher["values"]:
                return True
        elif matcher["type"] == "range":
            if matcher["low"] <= value <= matcher["high"]:
                return True
        else:
            assert False, "unexpected matcher type: {}".format(matcher["type"])
        return False

def get_queue_index(env):
    try:
        index = os.readlink(env["queue_current"])
    except OSError:
        min_value = math.inf
        for entry_path in env["queue"].iterdir():
            try:
                min_value = min(min_value, int(entry_path.name))
            except ValueError:
                continue
        index = min_value if min_value != math.inf else 0
    return index

def collect_matched_songs(env, matchers):
    songs = []
    matches_media = (
        apply_matchers(matchers["from"], MEDIA_PLAYLIST) and
        env["media"].is_dir())
    if matches_media:
        for artist_path in sorted(env["media"].iterdir()):
            artist = unescape_string(artist_path.name)
            if not apply_matchers(matchers["artist"], artist):
                continue
            if not artist_path.is_dir():
                continue
            for album_path in sorted(artist_path.iterdir()):
                album = unescape_string(album_path.name)
                if not apply_matchers(matchers["album"], album):
                    continue
                if not album_path.is_dir():
                    continue
                for song_path in sorted(album_path.iterdir()):
                    if song_path.suffix not in MEDIA_EXTENSIONS:
                        continue
                    if not song_path.is_file():
                        continue
                    metadata = parse_relpath(
                        song_path.relative_to(env["media"]))
                    disqualified = False
                    for field in ("disk", "track", "song", "extension"):
                        if not apply_matchers(
                                matchers[field], metadata[field]):
                            disqualified = True
                            break
                    if disqualified:
                        continue
                    songs.append(metadata)
    for playlist_path in sorted(env["playlists"].iterdir()):
        playlist = unescape_string(playlist_path.name)
        if not apply_matchers(matchers["from"], playlist):
            continue
        if not playlist_path.is_dir():
            continue
        offset = get_queue_index(env) if playlist == QUEUE_PLAYLIST else 0
        for entry_path in sorted(playlist_path.iterdir()):
            try:
                index = int(entry_path.name)
            except ValueError:
                continue
            index += offset
            if not apply_matchers(matchers["index"], index):
                continue
            if not entry_path.is_symlink():
                continue
            song_path = entry_path.resolve()
            relpath = song_path.relative_to(env["media"])
            metadata = parse_relpath(relpath)
            disqualified = False
            for field in ("artist", "album", "disk", "track", "song",
                          "extension"):
                if not apply_matchers(matchers[field], metadata[field]):
                    disqualified = True
                    break
            if disqualified:
                continue
            metadata["from"] = playlist
            metadata["index"] = index
            metadata["relpath"] = relpath
            songs.append(metadata)
    return metadata

def sort_songs(songs, sorters):
    for sorter in sorters:
        field = sorter["field"]
        modifier = sorter["modifier"]
        reverse = False
        assert modifier in ("sort", "reverse", "shuffle"), (
            "unexpected sort modifier: {}".format(modifier))
        if modifier == "shuffle":
            seed1 = random.getrandbits(64)
            seed2 = random.getrandbits(64)
            def key(value):
                return hash((seed1, value[field], seed2))
        else:
            def key(value):
                return value[field]
        reverse = modifier == "reverse"
        songs.sort(key=key, reverse=reverse)

CONTEXT = 3

def song_description(song, index):
    return ("\n  {}. {} ({}, {})"
            .format(index, song["song"], song["album"], song["artist"]))

CONTEXT_DIVIDER = "\n-----"

def insert_in_playlist(env, songs, playlist, index, before, yes):
    if playlist == QUEUE_PLAYLIST:
        current_index = get_queue_index(env)
        index += current_index
    playlist_path = env["playlists"] / playlist
    existing_indices = []
    for entry_path in playlist_path.iterdir():
        try:
            index = int(entry_path.name)
        except ValueError:
            continue
        existing_indices.append(index)
    existing_indices.sort()
    bisect_fn = bisect.bisect_left if before else bisect.bisect_right
    insertion_point = bisect_fn(index, existing_indices)
    insertion_list = []
    removals = []
    if playlist == QUEUE_PLAYLIST:
        insertion_point = bisect.bisect_left(current_index, existing_indices)
        for i in range(insertion_point - env["queue_length"]):
            index = existing_indices[i]
            removals.append(playlist_path / str(index))
    for i in range(max(0, insertion_point - CONTEXT), insertion_point):
        index = existing_indices[i]
        song = parse_relpath(
            (playlist_path / str(index)).resolve().relative_to(env["media"]))
        insertion_list.append(song_description(song, index))
    insertion_list.append(CONTEXT_DIVIDER)
    creates = []
    for offset, song in enumerate(songs):
        song_index = index + offset
        target = pathlib.Path("..") / ".." / MEDIA_PLAYLIST / song["relpath"]
        creates.append((playlist_path / str(song_index), target))
        insertion_list.append(song_description(song, song_index))
    insertion_list.append(CONTEXT_DIVIDER)
    for i in range(insertion_point,
                   min(insertion_point + CONTEXT, len(existing_indices))):
        index = existing_indices[i]
        song = parse_relpath(
            (playlist_path / str(index)).resolve().relative_to(env["media"]))
        insertion_list.append(song_description(song, index + len(songs)))
    renames = []
    for i in range(insertion_point, len(existing_indices)):
        old_index = existing_indices[i]
        new_index = old_index + len(songs)
        renames.append((playlist_path / str(old_index),
                        playlist_path / str(new_index)))
    renames.reverse()
    log(("will insert the following {} song{} into "
         "playlist {} with {} song{} already:{}")
        .format(*pluralens(songs), repr(playlist),
                *pluralens(existing_indices),
                "".join(insertion_list)))
    log("will move {} symlink{}, insert {}, prune {}"
        .format(*pluralens(renames), len(creates), len(removals)))
    if not are_you_sure(default=False, yes=yes):
        die()
    for removal in removals:
        removal.unlink()
    for rename, target in renames:
        rename.rename(target)
    for create, target in creates:
        create.symlink_to(target)

def insert_songs(
        env, matchers, sorters, playlist, index, transfer, before, yes):
    if transfer:
        raise NotImplementedError
    songs = collect_matched_songs(env, matchers)
    sort_songs(songs, sorters)
    insert_in_playlist(env, songs, playlist, index, before=before, yes=yes)

def handle_args(args):
    home = os.environ.get(FSTUNES_HOME_ENV_VAR)
    if not home:
        die("environment variable not set: {}".format(FSTUNES_HOME_ENV_VAR))
    home = pathlib.Path(home)
    if not home.is_dir():
        if home.exists() or home.is_symlink():
            die("not a directory: {}".format(home))
        die("directory does not exist: {}".format(home))
    queue_length = os.environ.get(FSTUNES_QUEUE_LENGTH_ENV_VAR)
    if queue_length:
        try:
            queue_length = int(queue_length)
        except ValueError:
            die("invalid integer literal in {}: {}"
                .format(FSTUNES_QUEUE_LENGTH_ENV_VAR, queue_length))
        if queue_length < 0:
            die("queue length cannot be negative in {}: {}"
                .format(FSTUNES_QUEUE_LENGTH_ENV_VAR, queue_length))
    else:
        queue_length = 10000
    env = {
        "home": home,
        "media": home / MEDIA_PLAYLIST,
        "playlists": home / "playlists",
        "queue": home / "playlists" / QUEUE_PLAYLIST,
        "queue_current": home / "playlists" / QUEUE_PLAYLIST / "_current",
        "queue_length": queue_length,
    }
    if args.subcommand == "import":
        import_music(env, args.paths)
    elif args.subcommand == "playlist":
        if args.subcommand_playlist == "create":
            create_playlists(env, args.playlists)
        else:
            delete_playlists(env, args.playlists, yes=args.yes)
    elif args.subcommand == "insert":
        matchers = parse_matchers(args)
        sorters = parse_sorters(args)
        insert_songs(
            matchers, sorters, args.playlist, args.index,
            transfer=args.transfer, before=args.before, yes=args.yes)
    else:
        raise NotImplementedError

def main():
    parser = get_parser()
    args = parser.parse_args()
    handle_args(args)
