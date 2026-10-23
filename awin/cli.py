"""The `awin` command: read a request, ask a person, map the answer to an exit code."""
import argparse
import contextlib
import json
import sys

from awin import __version__, window
from awin.request import InvalidRequest, parse

EXIT_APPROVED, EXIT_CANCELLED, EXIT_INVALID, EXIT_UNAVAILABLE = 0, 1, 2, 3


def _timeout(value: str) -> int:
    try:
        seconds = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("not an integer: %r" % value)
    if not 1 <= seconds <= window.MAX_TIMEOUT:
        raise argparse.ArgumentTypeError(
            "must be between 1 and %d" % window.MAX_TIMEOUT)
    return seconds


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="awin",
        description="Show a native approval window; exit 0 approved, 1 cancelled, "
                    "2 invalid input, 3 no window available.")
    parser.add_argument("--spec", metavar="FILE",
                        help="read the JSON request from FILE instead of stdin")
    parser.add_argument("--timeout", metavar="SECONDS", type=_timeout,
                        default=window.DEFAULT_TIMEOUT,
                        help="seconds to wait (1-%d; can lower, never raise)"
                             % window.MAX_TIMEOUT)
    parser.add_argument("--version", action="version", version="awin " + __version__)
    return parser


def _read(args, stdin) -> object:
    if args.spec:
        try:
            with open(args.spec, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            raise InvalidRequest("cannot read spec file: %s" % exc.strerror)
    else:
        raw = stdin.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise InvalidRequest("input is not valid UTF-8")
    except (ValueError, RecursionError):
        raise InvalidRequest("input is not valid JSON")


def main(argv, stdin=None, stdout=None, stderr=None, asker=None, is_available=None) -> int:
    stdin = sys.stdin.buffer if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    asker = asker or window.ask
    is_available = is_available or window.available

    def fail(code, message):
        print("awin: " + " ".join(str(message).split()), file=stderr)
        return code

    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            args = build_parser().parse_args(argv)
    except _UsageError as exc:
        return fail(EXIT_INVALID, exc)
    except SystemExit as exc:  # -h / --version
        return EXIT_APPROVED if exc.code in (0, None) else EXIT_INVALID

    try:
        with contextlib.redirect_stderr(stderr):  # parse() prints its own warnings
            req = parse(_read(args, stdin))
    except InvalidRequest as exc:
        return fail(EXIT_INVALID, exc)

    if not is_available():
        return fail(EXIT_UNAVAILABLE, "no approval window available (needs macOS and /usr/bin/osascript)")
    try:
        approved = asker(req, args.timeout)
    except window.Unavailable as exc:
        return fail(EXIT_UNAVAILABLE, exc or "no approval window available")

    if approved is True:
        print("approved", file=stdout)
        return EXIT_APPROVED
    print("cancelled", file=stdout)
    return EXIT_CANCELLED
