import argparse
import mutagen
import os
import pathlib
import re
import shutil
import string
import sys

def has_duplicates(l):
    return len(l) != len(set(l))

def iter_len(iterable):
    return sum(1 for _ in iterable)

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
    parser.add_argument("-f", "--fields", nargs="+",
                        help="Which metadata fields to include")

def add_match_options(parser):
    parser.add_argument("-m", "--match", nargs="*", metavar="FIELD=EXPR",
                        help="Filter songs")
    parser.add_argument("--match-literal", nargs="*", metavar="FIELD=VALUE",
                        help="Filter songs by literal match")
    parser.add_argument("--match-set", nargs="*",
                        metavar="FIELD=VALUE1,VALUE2,...",
                        help="Filter songs by set membership")
    parser.add_argument("--match-range", nargs="*", metavar="FIELD=LOW-HIGH",
                        help="Filter songs by range inclusion")
    parser.add_argument("--match-all", nargs="*",
                        help="Do not filter songs")

    parser.add_argument("--set-delimiter", default=",",
                        help="Delimiter to use for set filtering")
    parser.add_argument("--range-delimiter", default="-",
                        help="Delimiter to use for range filtering")

def add_sort_options(parser):
    parser.add_argument("-s", "--sort", nargs="*", help="Sort by field")
    parser.add_argument("-r", "--reverse", nargs="*",
                        help="Sort by field in reverse order")
    parser.add_argument("-x", "--shuffle", nargs="*",
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
        "index", help="Index at which to insert")

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
        "index", nargs="?", help="Relative index to which to seek")

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

def import_song(filepath, env):
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

def plural(n):
    return "s" if n != 1 else ""

MEDIA_EXTENSIONS = [".mp3"]

def import_music(paths, env):
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
                if import_song(filepath, env):
                    copied += 1
                else:
                    already_present += 1
    log(("imported {} media file{}, skipped {} "
         "already present and {} unrecognized")
        .format(copied, plural(copied), already_present, skipped))

def create_playlists(playlists, env):
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
    log("created {} playlist{}".format(len(playlists), plural(len(playlists))))

def delete_playlists(playlists, env, yes):
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
        num_songs = iter_len(path.iterdir())
        total_songs += num_songs
        deletion_list.append(
            "\n  {} ({} song{})"
            .format(playlist, num_songs, plural(num_songs)))
    log("will delete the following {} playlist{} with {} total songs:{}"
        .format(len(paths), plural(len(paths)),
                total_songs, "".join(deletion_list)))
    if not are_you_sure(default=total_songs == 0, yes=yes):
        die()
    for path in paths:
        shutil.rmtree(path)
    log("deleted {} playlist{}".format(len(playlists), plural(len(playlists))))

FSTUNES_HOME_ENV_VAR = "FSTUNES_HOME"

def handle_args(args):
    home = os.environ.get(FSTUNES_HOME_ENV_VAR)
    if not home:
        die("environment variable not set: {}".format(FSTUNES_HOME_ENV_VAR))
    home = pathlib.Path(home)
    if not home.is_dir():
        if home.exists() or home.is_symlink():
            die("not a directory: {}".format(home))
        die("directory does not exist: {}".format(home))
    env = {
        "home": home,
        "media": home / "media",
        "playlists": home / "playlists",
    }
    if args.subcommand == "import":
        import_music(args.paths, env)
    elif args.subcommand == "playlist":
        if args.subcommand_playlist == "create":
            create_playlists(args.playlists, env)
        else:
            delete_playlists(args.playlists, env, yes=args.yes)
    else:
        die("not yet implemented: {}".format(args.subcommand))

def main():
    parser = get_parser()
    args = parser.parse_args()
    handle_args(args)
