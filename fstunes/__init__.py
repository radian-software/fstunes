import argparse

def add_yes_option(parser):
    parser.add_argument("-y", "--yes", help="Don't ask for confirmation",
                        action="store_true")

def add_fields_option(parser):
    parser.add_argument("-f", "--fields", nargs="+")

def add_match_options(parser):
    parser.add_argument("-m", "--match", nargs="*")
    for match_type in (
            "--match-literal",
            "--match-set",
            "--match-range",
            "--match-all"):
        parser.add_argument(match_type, nargs="*")
    parser.add_argument("--set-delimiter")
    parser.add_argument("--range-delimiter")

def add_sort_options(parser):
    parser.add_argument("-s", "--sort", nargs="*")
    parser.add_argument("-r", "--reverse", nargs="*")
    parser.add_argument("-x", "--shuffle", nargs="*")

def get_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Minimal command-line music library manager and media player."))
    subparsers = parser.add_subparsers()

    parser_import = subparsers.add_parser(
        "import", help="Add media files to library")
    parser_import.add_argument("path", nargs="+")

    parser_playlist = subparsers.add_parser(
        "playlist", help="Create or delete playlists")
    subparsers_playlist = parser_playlist.add_subparsers()

    parser_playlist_create = subparsers_playlist.add_parser(
        "create", help="Create a playlist")
    parser_playlist_create.add_argument("playlist", nargs="+")

    parser_playlist_delete = subparsers_playlist.add_parser(
        "delete", help="Delete a playlist")
    parser_playlist_delete.add_argument("playlist", nargs="+")
    add_yes_option(parser_playlist_delete)

    parser_insert = subparsers.add_parser(
        "insert", help="Add songs to a playlist or the queue")
    add_match_options(parser_insert)
    add_sort_options(parser_insert)
    parser_insert.add_argument("-t", "--transfer", action="store_true")
    add_yes_option(parser_insert)

    group_insert_before = parser_insert.add_mutually_exclusive_group()
    group_insert_before.add_argument("--before", action="store_false")
    group_insert_before.add_argument(
        "--after", action="store_true", dest="before")

    parser_insert.add_argument("playlist")
    parser_insert.add_argument("index")

    parser_remove = subparsers.add_parser(
        "remove", help="Remove songs from a playlist or the queue")
    add_match_options(parser_remove)
    add_yes_option(parser_remove)

    parser_edit = subparsers.add_parser(
        "edit", help="Edit song metadata")
    add_match_options(parser_edit)
    add_sort_options(parser_edit)
    add_fields_option(parser_edit)
    parser_edit.add_argument("-e", "--editor")
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
    group_seek_play_pause.add_argument("-p", "--play", action="store_true")
    group_seek_play_pause.add_argument("-P", "--pause", action="store_true")

    parser_seek.add_argument("index", nargs="?")

    return parser

def main():
    parser = get_parser()
    parser.parse_args()
