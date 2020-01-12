from argparse import ArgumentParser
from pathlib import Path
import os
import shlex
import sys

import numpy as np
import h5py
from prompt_toolkit import PromptSession, print_formatted_text, HTML
from prompt_toolkit.completion import Completer, Completion


def directory(s):
    return f'<b><ansibrightblue>{s}</ansibrightblue></b>'


COMMANDS = ['attrs', 'cat', 'cd', 'cp', 'exit', 'help', 'ls', 'mkdir', 'mv', 'pwd', 'rm']


class CommandCompleter(Completer):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def get_completions(self, document, complete_event):
        words = document.text.split()
        n = len(words)
        if n == 0:
            return
        word = document.get_word_under_cursor()
        if n == 1 and word:
            for cmd in COMMANDS:
                if cmd.startswith(word):
                    yield Completion(cmd, -len(word))
        else:
            cmd = words[0]
            if cmd in ('cd', 'ls'):
                gen = self.state.completions(word, h5py.Group)
            else:
                gen = self.state.completions(word)
            for item in gen:
                yield Completion(item, -len(word))


class H5FileState:
    def __init__(self, fh):
        self.f = fh
        self.group = self.f
        self.last_group = self.group

    def abspath(self, path=''):
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

    def completions(self, path, nodetype=None):
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


def attrs(args, state):
    """Display attribute on a Dataset/Group

    Parameters
    ----------
    args : list of str
        path of Dataset/Group

    """
    # Check that argument was given
    if not args:
        help(['attrs'])
        return

    path = state.abspath(args[0])
    if path in state.f:
        obj = state.f[path]
        print(dict(obj.attrs.items()))
    else:
        print(f'attrs: {path}: No such object')


def cat(args, state):
    """Display data in a Dataset

    Parameters
    ----------
    arg : str
        path of Dataset

    """

    # Check that argument was given
    if not args:
        help(['cat'])
        return
    # If -f option given, show all data in Dataset
    if '-f' in args[:-1]:
        np.set_printoptions(threshold=np.nan)

    lastarg = args[-1]
    path = state.abspath(lastarg)
    if path in state.f:
        dataset = state.f[path]
        if isinstance(dataset, h5py.Dataset):
            print(dataset[()])
        else:
            print(f'cat: {lastarg}: Not a dataset')
    else:
        print(f'cat: {lastarg}: No such dataset')

    # If -f option given, reset numpy threshold print option
    if '-f' in args[:-1]:
        np.set_printoptions(threshold=1000)


def cd(arg, state):
    """Change the current group

    Parameters
    ----------
    arg : str
        absolute or relative path

    """

    # As in bash, - indicates the previous group
    if arg == '-':
        group = state.last_group
        state.last_group = state.group
        state.group = group
        #state.prompt = os.path.basename(state.group.name) + '> '
        return

    # Get absolute path name
    path = state.abspath(arg)
    if path in state.f:
        group = state.f[path]
        # Check if given path is a group
        if isinstance(group, h5py.Group):
            state.last_group = state.group
            state.group = group
            #state.prompt = os.path.basename(state.group.name) + '> '
        else:
            print(f'cd: {arg}: Not a group')
    else:
        print(f'cd: {arg}: No such group')


def cp(args, state):
    """Copy a dataset or group

    Parameters
    ----------
    args : str
        arguments to cp command

    """

    # Check that file is writable
    if state.f.mode != 'r+':
        print('cp: HDF5 file is not open in read/write mode')
        return

    # Make sure enough arguments were specified
    if len(args) < 2:
        print(f"cp: missing destination operand after `{args}'")
        return

    # Get absolute paths
    dest = state.abspath(args[-1])

    # For 3+ argument form, destination must be a group
    if ((dest in state.f and isinstance(state.f[dest], h5py.Dataset))
        or dest not in state.f) and len(args) > 2:
        print(f"cp: target `{args[-1]}' is not a group")
        return

    for source in map(state.abspath, args[:-1]):
        # Check that source exists
        if source not in state.f:
            print(f'cp: {args[0]}: No such group or dataset')
            continue

        # Modify destination if it is a group
        if dest in state.f and isinstance(state.f[dest], h5py.Group):
            final_dest = dest + os.path.basename(source.rstrip('/'))
        else:
            final_dest = dest

        # If destination exists, delete it first
        if final_dest in state.f:
            del state.f[final_dest]

        # Copy source to destination
        state.f.copy(source, final_dest)


def ls(arg, state):
    """List contents of current group

    Parameters
    ----------
    arg : str, optional
        absolute or relative path

    """

    # Get absolute path -- note that if no argument is given, abpath returns
    # the path to the current group
    path = state.abspath(arg)

    path_node = state.f[path]
    # Check to make sure path is a group
    if not isinstance(path_node, h5py.Group):
        print(f'ls: {arg} is not a group')
        return

    # Check to make sure path is in file
    if path in state.f:
        nodes = list(path_node.values())
    else:
        print(f'ls: {arg}: No such group')
        return

    # The vals list contains tuples contain (datatype, size of data, name) and
    # the lengths dictionary specifies the maximum length of each column
    vals = [('group', '1', directory('.')),
            ('group', '1', directory('..'))]
    lengths = {'dtype': 5, 'size': 1 , 'name': 2}

    for node in nodes:
        # For each value in group, determine datatype, size, and name
        basename = os.path.basename(node.name)
        if isinstance(node, h5py.Group):
            dtype = 'group'
            size = '1'
            name = directory(basename)
        elif isinstance(node, h5py.Dataset):
            dtype = node.dtype.name
            size = str(node.shape)
            name = basename
        vals.append((dtype, size, name))

        # Adjust size of columns as necessary
        lengths['dtype'] = max(lengths['dtype'], len(dtype))
        lengths['size'] = max(lengths['size'], len(dtype))
        lengths['name'] = max(lengths['name'], len(dtype))

    # Create str.format specification for three columns
    spec = '{{0:{0[dtype]}}}  {{1:>{0[size]}}}  {{2:{0[name]}}}'.format(lengths)

    # Display each value in the group
    for dtype, size, name in sorted(vals, key=lambda x: x[2]):
        print_formatted_text(HTML(spec.format(dtype, size, name)))


def mkdir(args, state):
    """Create a new group

    Parameters
    ----------
    arg : str
        absolute or relative path

    """

    # Check that file is writable
    if state.f.mode != 'r+':
        print('mkdir: HDF5 file is not open in read/write mode')
        return

    for arg in args:
        path = state.abspath(arg)
        if path in state.f:
            print(f"mkdir: cannot create group `{arg}': Groups exists")
        else:
            # Create group
            state.f.create_group(path)


def mv(args, state):
    """Move a dataset or group

    Parameters
    ----------
    arg : str
        arguments to mv command

    """

    # Check that file is writable
    if state.f.mode != 'r+':
        print('mv: HDF5 file is not open in read/write mode')
        return

    # Make sure enough arguments were specified
    if len(args) < 2:
        print(f"mv: missing destination operand after `{args[0]}'")
        return

    # Get absolute paths
    dest = state.abspath(args[-1])

    # For 3+ argument form, destination must be a group
    if ((dest in state.f and isinstance(state.f[dest], h5py.Dataset))
        or dest not in state.f) and len(args) > 2:
        print(f"mv: target `{args[-1]}' is not a group")
        return

    for source in map(state.abspath, args[:-1]):
        # Check that source exists
        if source not in state.f:
            print(f'mv: {args[0]}: No such group or dataset')
            continue

        # Modify destination if it is a group
        if dest in state.f and isinstance(state.f[dest], h5py.Group):
            final_dest = dest + os.path.basename(source.rstrip('/'))
        else:
            final_dest = dest

        # If destination exists, delete it first
        if final_dest in state.f:
            del state.f[final_dest]

        # Copy source to destination
        state.f.copy(source, final_dest)
        del state.f[source]


def pwd(state):
    """Display the path of the current group"""
    print(state.group.name)


def rm(args, state):
    """Remove a dataset or group

    Parameters
    ----------
    arg : str
        absolute or relative path

    """

    # Check that file is writable
    if state.f.mode != 'r+':
        print('rm: HDF5 file is not open in read/write mode')
        return

    for arg in args:
        path = state.abspath(arg)
        if path not in state.f:
            print(f'rm: {arg}: No such group or dataset')
        else:
            # Delete path
            del state.f[path]


_HELP_MESSAGES = {
    'attrs': 'Display attributes of a dataset or group',
    'cat': 'Display a dataset',
    'cd': 'Change the current group',
    'cp': 'Copy a dataset or group',
    'exit': 'Exit the HDF5 shell',
    'help': 'Display information about a command',
    'ls': 'Display a listing of groups and dataset within the current group',
    'mkdir': 'Create a new group',
    'mv': 'Move a dataset or group',
    'pwd': 'Display the current group',
    'rm': 'Remove a dataset or group',
}


def help(args):
    if not args:
        print("Commands:\n")
        for cmd in COMMANDS:
            print(f"{cmd:6} -- {_HELP_MESSAGES[cmd]}")
    else:
        cmd = args[0]
        if cmd not in _HELP_MESSAGES:
            print(f"help: `{cmd}' is not a valid command")
        print(_HELP_MESSAGES[cmd])


def main():
    # Set up command-line argument parser
    parser = ArgumentParser()
    parser.add_argument('-w', '--write', dest='write', action='store_true',
                        default=False, help="Open HDF5 in read/write mode")
    parser.add_argument('filename', help="HDF5 filename")
    args = parser.parse_args()

    if not Path(args.filename).is_file():
        sys.exit(f'h5sh: {args.filename}: Not a valid HDF5 file')

    # Open HDF5 in read/write mode
    mode = 'a' if args.write else 'r'
    with h5py.File(args.filename, mode) as fh:
        state = H5FileState(fh)
        session = PromptSession()

        while True:
            try:
                text = session.prompt('> ', completer=CommandCompleter(state),
                                      complete_while_typing=False)
            except EOFError:
                break

            words = shlex.split(text)
            if words:
                cmd, *args = words
                if cmd == 'attrs':
                    attrs(args, state)
                elif cmd == 'cat':
                    cat(args, state)
                elif cmd == 'cp':
                    cp(*args, state)
                elif cmd == 'cd':
                    cd(' '.join(args), state)
                elif cmd == 'exit':
                    break
                elif cmd == 'help':
                    help(args)
                elif cmd == 'ls':
                    ls(' '.join(args), state)
                elif cmd == 'mkdir':
                    mkdir(args, state)
                elif cmd == 'mv':
                    mv(args, state)
                elif cmd == 'pwd':
                    pwd(state)
                elif cmd == 'rm':
                    rm(args, state)

if __name__ == '__main__':
    main()
