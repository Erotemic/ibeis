from ibeis.tests.demodata_registery import DemoDataRegistry

DEMODATA = DemoDataRegistry(appname='ibeis')
DEMODATA.register(
    **{
        'key': 'testdb1',
        'fname': 'testdata.zip',
        'url': 'https://data.kitware.com/api/v1/file/68aa804908a548e171789a8e/download',
        'note': 'the ibeis simple testdata.',
        'mirrors': [
            # 'https://cthulhu.dyn.wildme.io/public/data/testdata.zip',  # Old and broken
        ],
        'ipfs_cids': [
            'bafybeiemhexooztry66opieszfhfb2v4af7ittx32vxqtaffjnhqaez5yi',
        ],
        'sha256': '597a733c5990372e78ac1aba2f950737037016a35521f2bdca94b82f29b7c4b9',
        'sha512': 'fd1b571fc92c403002b5df223971e2453abea5601629d028b718aead281f1bd5a3680bc0c74c7ba3d28a6505566074bb1ec2a3060d11d9d4da94c0d80dfb01ae',
        'properties': {
        },
    }
)


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/ibeis/ibeis/tests/demodata2.py
    """
    import scriptconfig
    import inspect

    class UpdateCLI(scriptconfig.DataConfig):
        __default__ = {
            p.name: p.default for p in inspect.signature(DEMODATA.update_hashes).parameters.values()
        }
        @classmethod
        def main(cls, argv=None, **kwargs):
            config = cls.cli(strict=True, argv=argv, data=kwargs, verbose='auto')
            DEMODATA.update_hashes(**config)

    UpdateCLI.main()
