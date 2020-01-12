import os
import re
from typing import Iterator

import h5py
from prompt_toolkit.completion import Completer, Completion
import prompt_toolkit.document

from . import commands

# Monkey patch regular expression used to figure out if the cursor is on a word.
# Namely, include / and . in the regex so that paths are considered "words"
prompt_toolkit.document._FIND_CURRENT_WORD_RE = re.compile(
    r"^([a-zA-Z0-9_/.]+|[^a-zA-Z0-9_/.\s]+)")


class CommandCompleter(Completer):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def get_completions(self, document, complete_event):
        """Get word completions."""
        words = document.text.split()
        n = len(words)
        if n == 0:
            return
        word = document.get_word_under_cursor()
        if n == 1 and word:
            for cmd in commands.COMMANDS:
                if cmd.startswith(word):
                    yield Completion(cmd, -len(word))
        else:
            cmd = words[0]
            if cmd in {'cd', 'ls'}:
                gen = self.state.completions(word, h5py.Group)
            elif cmd in {'exit', 'help', 'pwd'}:
                return
            else:
                gen = self.state.completions(word)
            for item in gen:
                yield Completion(item, -len(word))


class H5FileState:
    """Stores the HDF5 file and information about the current/last group."""


    def __init__(self, fh: h5py.File):
        self.f = fh
        self.group = self.f
        self.last_group = self.group

    def abspath(self, path: str = '') -> str:
        """Absolute path in HDF5 file

        Parameters
        ----------
        path : str
            absolute or relative path

        """

        # Determine absolute path given relative path
        if path.startswith('/'):
            # Path is already absolute
            abspath = path
        else:
            abspath = os.path.abspath(os.path.join(self.group.name, path))

        # Check if absolute path is a group and if so, append '/'
        if abspath in self.f:
            if isinstance(self.f[abspath], h5py.Group):
                if not abspath.endswith('/'):
                    abspath += '/'

        return abspath

    def completions(self, path: str, nodetype=None) -> Iterator[str]:
        """Determine completions given a partial path

        Parameters
        ----------
        path : str
            absolute or relative path
        nodetype : Group or Dataset class
            class to match for completions

        """

        abspath = self.abspath(path)

        # Since the 'path' variable is used as a prefix later, if it is determined
        # that the path is a group. add a '/' at the end of it
        if abspath.endswith('/') and not path.endswith('/') and path:
            path += '/'

        # Get the directory and base name of the specified path
        dirname = os.path.dirname(abspath)
        basename = os.path.basename(abspath)

        for node in self.f[dirname].values():
            # If node is a group, add a '/' suffix
            suffix = '/' if isinstance(node, h5py.Group) else ''

            # Skip nodes which don't match specified nodetype
            if not nodetype or isinstance(node, nodetype):
                # Determine basename of current node
                node_basename = os.path.basename(node.name)

                # Only add to completion if basename of specified path is contained
                # in basename of node
                if node_basename.startswith(basename):
                    prefix = os.path.dirname(path)
                    if prefix:
                        # Rather tha nusing basename, we use the directory name of
                        # 'path' since it might be something like ../../. Note that
                        # the .replace() method was added to treat the case where the
                        # specified path is '/'
                        yield (prefix + '/' + node_basename + suffix).replace('//', '/')
                    else:
                        # For relative paths, we don't need to add a prefix
                        yield node_basename + suffix
