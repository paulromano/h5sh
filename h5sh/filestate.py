import os

import h5py


class FileState:
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
