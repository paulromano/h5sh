import os
from typing import List, Optional

import h5py
import numpy as np
from prompt_toolkit import print_formatted_text, HTML

from .interpreter import H5FileState

COMMANDS = ['attrs', 'cat', 'cd', 'cp', 'exit', 'help', 'ls', 'mkdir', 'mv', 'pwd', 'rm']


def attrs(args: List[str], state: H5FileState) -> None:
    """Display attribute on a Dataset/Group

    Parameters
    ----------
    args
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


def cat(args: List[str], state: H5FileState) -> None:
    """Display data in a Dataset

    Parameters
    ----------
    args
        paths of Datasets

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


def cd(args: List[str], state: H5FileState) -> None:
    """Change the current group

    Parameters
    ----------
    arg : str
        absolute or relative path

    """

    # As in bash, - indicates the previous group
    arg = ' '.join(args)
    if arg == '-':
        group = state.last_group
        state.last_group = state.group
        state.group = group
        return

    # Get absolute path name
    path = state.abspath(arg)
    if path in state.f:
        group = state.f[path]
        # Check if given path is a group
        if isinstance(group, h5py.Group):
            state.last_group = state.group
            state.group = group
        else:
            print(f'cd: {arg}: Not a group')
    else:
        print(f'cd: {arg}: No such group')


def cp(args: List[str], state: H5FileState) -> None:
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


def ls(args: List[str], state: H5FileState) -> None:
    """List contents of current group

    Parameters
    ----------
    arg : str
        absolute or relative path

    """

    # Get absolute path -- note that if no argument is given, abpath returns
    # the path to the current group
    arg = ' '.join(args)  # TODO: Treat arguments separately
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

    def directory(s):
        return f'<b><ansibrightblue>{s}</ansibrightblue></b>'

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


def mkdir(args: List[str], state: H5FileState) -> None:
    """Create a new group

    Parameters
    ----------
    args
        absolute or relative paths

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


def mv(args: List[str], state: H5FileState) -> None:
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


def pwd(args: List[str], state: H5FileState) -> None:
    """Display the path of the current group"""
    print(state.group.name)


def rm(args: List[str], state: H5FileState) -> None:
    """Remove a dataset or group

    Parameters
    ----------
    args
        absolute or relative paths

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


def help(args: List[str], state: Optional[H5FileState] = None) -> None:
    """Show help information."""
    if not args:
        print("Commands:\n")
        for cmd in COMMANDS:
            print(f"{cmd:6} -- {_HELP_MESSAGES[cmd]}")
    else:
        cmd = args[0]
        if cmd not in _HELP_MESSAGES:
            print(f"help: `{cmd}' is not a valid command")
        print(_HELP_MESSAGES[cmd])
