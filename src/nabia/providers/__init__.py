"""Provider integrations, one self-contained subpackage per API.

Each subpackage follows the same layout (see
``docs/adding-a-provider.md``)::

    <provider>/
        README.md   endpoints, terms of use, quirks
        config.py   settings (env prefix NABIA_<PROVIDER>_)
        mapping.py  equivalence table(s): canonical <-> native names
        schemas.py  raw response models mirroring the upstream JSON
        parser.py   raw schemas -> normalized Nabia models
        client.py   public client class

Provider packages must stay cheap to import: heavy optional
dependencies are imported lazily inside the functions that need them.
"""
