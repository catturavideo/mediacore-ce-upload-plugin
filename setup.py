from setuptools import setup, find_packages

setup(
    name = 'MediaCore-Upload-API',
    version = '1.0.0',
    packages = find_packages(),
    author = 'Gregory Marco',
    author_email = 'greg@catturavideo.com',
    description = 'Implements the MediaCore upload API.',
    zip_safe = False,
    install_requires = [
        'MediaCore >= 0.9.0b1'
    ],
    entry_points = '''
        [mediacore.plugin]
        upload_api=mediacore_upload
    ''',
    message_extractors = {},
)
