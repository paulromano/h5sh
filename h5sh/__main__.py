from argparse import ArgumentParser
from configparser import ConfigParser
import os
from pathlib import Path
import shlex
import sys

import h5py
from prompt_toolkit import PromptSession

from . import commands
from .completions import CommandCompleter
from .filestate import FileState


def main() -> None:
    # Set up command-line argument parser
    parser = ArgumentParser()
    parser.add_argument('-w', '--write', dest='write', action='store_true',
                        default=False, help="Open HDF5 in read/write mode")
    parser.add_argument('filename', help="HDF5 filename")
    args = parser.parse_args()

    if not Path(args.filename).is_file():
        sys.exit(f'h5sh: {args.filename}: Not a valid HDF5 file')

    # Read aliases from .h5rc file
    config = ConfigParser()
    config.read(os.getenv('HOME') + '/.h5rc')
    alias_table = config['ALIASES'] if 'ALIASES' in config else {}

    # Open HDF5 in read/write mode
    mode = 'a' if args.write else 'r'
    with h5py.File(args.filename, mode) as fh:
        state = FileState(fh)
        session = PromptSession()

        while True:
            try:
                text = session.prompt('> ',
                    completer=CommandCompleter(state),
                    complete_while_typing=False,
                    bottom_toolbar=f"Current group: {state.group.name}",
                )
            except EOFError:
                break

            words = shlex.split(text)
            if words:
                cmd, *args = words
                if cmd == 'exit':
                    break

                # Check for alias
                cmd = alias_table.get(cmd, cmd)

                try:
                    func = getattr(commands, cmd)
                except AttributeError:
                    print(f"{cmd}: command not found")
                else:
                    func(args, state)


if __name__ == "__main__":
    main()
