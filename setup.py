from setuptools import setup

kwargs = {
    'name': 'h5sh',
    'version': '0.1.0',
    'packages': ['h5sh'],
    'entry_points': {
        'console_scripts': [
            'h5sh = h5sh.__main__:main'
        ]
    },

    # Metadata
    'author': 'Paul Romano',
    'author_email': 'paul.k.romano@gmail.com',
    'description': 'h5sh',
    'url': 'https://github.com/paulromano/h5sh',
    'download_url': 'https://github.com/paulromano/h5sh/releases',
    'project_urls': {
        'Issue Tracker': 'https://github.com/paulromano/h5sh/issues',
        'Source Code': 'https://github.com/paulromano/h5sh',
    },
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Topic :: Scientific/Engineering'
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    # Dependencies
    'python_requires': '>=3.6',
    'install_requires': [
        'numpy', 'h5py', 'prompt_toolkit'
    ],
}

setup(**kwargs)
