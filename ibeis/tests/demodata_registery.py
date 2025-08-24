import ubelt as ub


class DemoDataRegistry:
    """
    Minimal registry for downloadable demo data (any file type).

    Features:
        * Register by keyword-args or dict.
        * Download/caching via :func:`ubelt.grabdata`.
        * Optional hash verification (sha256 / sha512) via grabdata's
          ``hash_prefix``.
        * Fallback to mirrors (and IPFS gateway expansion from ``ipfs_cids``).

    Notes:
        This mirrors patterns used in an existing demodata helper:
        - Use ``hash_prefix`` / ``hasher`` with :func:`ubelt.grabdata`
          when hashes are available:contentReference[oaicite:1]{index=1}.
        - Try primary URL first, then mirrors on failure:contentReference[oaicite:2]{index=2}.
        - Expand ``ipfs_cids`` into HTTP gateway mirrors:contentReference[oaicite:3]{index=3}.

    Args:
        appname (str):
            Application name for the on-disk cache namespace. Passed to
            :func:`ubelt.grabdata` via the ``appname`` kwarg.

        hasher_priority (tuple[str, ...]):
            Order of hash preference if multiple hashes are present on an item.

        ipfs_gateways (str | tuple[str, ...]):
            If ``'default'``, uses a small set of public gateways. Otherwise, a
            tuple of gateway base URLs like ``('https://ipfs.io/ipfs', ...)``.
            Used to expand ``ipfs_cids`` into HTTP mirrors.

    Examples:
        Register by kwargs and download

        >>> # xdoctest: +REQUIRES(--network)
        >>> from ibeis.tests.demodata_registery import *  # NOQA
        >>> from ibeis.tests.demodata_registery import _grab_with_mirrors
        >>> reg = DemoDataRegistry(appname='ubelt/demodata')
        >>> reg.register(
        ...     key='airport',
        ...     url=('https://upload.wikimedia.org/wikipedia/commons/9/9e/'
        ...          'Beijing_Capital_International_Airport_on_18_February_2018_-_SkySat_%281%29.jpg'),
        ...     fname='airport.jpg',
        ...     # Known-good sha256 (from a maintained demodata manifest)
        ...     sha256=('bff5f9212d5c77dd47f2b80e5dc1b4409fa7813b08fc39b5'
        ...             '04294497b3483ffc'),
        ... )
        >>> fpath = reg.grab('airport')
        >>> assert ub.Path(fpath).exists()

        Register by dict

        >>> item = {
        ...     'url': 'https://data.kitware.com/api/v1/file/647cfb85a71cc6eae69303ad/download',
        ...     'fname': 'amazon.jpg',
        ...     'sha256': ('ef352b60f2577692ab3e9da19d09a49fa9da9937f892afc4'
        ...                '8094988a17c32dc3'),
        ... }
        >>> reg.register('amazon', **item)
        >>> info = reg.info('amazon')
        >>> assert info['fname'] == 'amazon.jpg'

        Mirrors and IPFS (demonstration)

        >>> reg.register(
        ...     key='astro',
        ...     url='https://i.imgur.com/KXhKM72.png',
        ...     fname='astro.png',
        ...     mirrors=['https://data.kitware.com/api/v1/file/647cfb78a71cc6eae69303a7/download'],
        ...     ipfs_cids=['bafybeif2w42xgi6vkfuuwmn3c6apyetl56fukkj6wnfgzcbsrpocciuv3i'],
        ...     sha256='9f2b4671e868fd51451f03809a694006425eee64ad472f7065da04079be60c53',
        ... )
        >>> # fpath = reg.grab('astro')  # xdoctest: +SKIP

        Hash behavior

        >>> reg.register(key='nohash', url='https://example.com/file.dat', fname='file.dat')
        >>> try:
        ...     _ = reg.grab('nohash', require_hash=True)
        ...     ok = False
        ... except ValueError:
        ...     ok = True
        >>> assert ok

        Utility API

        >>> isinstance(list(reg.keys()), list)
        True
        >>> 'airport' in reg
        True
        >>> len(reg) >= 2
        True
    """

    def __init__(self, appname: str = "demodata",
                 hasher_priority=("sha256", "sha512"),
                 ipfs_gateways='default'):
        self._registry = {}
        self.appname = appname
        self.hasher_priority = tuple(hasher_priority)
        if ipfs_gateways == 'default':
            ipfs_gateways = (
                "https://ipfs.io/ipfs",
                "https://dweb.link/ipfs",
            )
        self.ipfs_gateways = tuple(ipfs_gateways)

    # ---- registration / inspection

    def register(self, key=None, **item):
        """
        Register a single item.

        Args:
            key (str | None): Explicit key. If omitted, the stem of ``fname`` is used.
            **item: Must include at least ``url``. Optional: ``fname``, ``mirrors``,
                ``ipfs_cids``, ``sha256``, ``sha512``, ``note`` (free text), etc.

        Raises:
            ValueError: If neither ``key`` is provided nor ``fname`` present, or missing ``url``.
        """
        if key is None:
            fname = item.get("fname", None)
            if not fname:
                raise ValueError("Must specify a key or include 'fname' to derive one")
            key = ub.Path(fname).stem
        if "url" not in item:
            raise ValueError("Registered item must include a 'url'")
        self._registry[key] = dict(item)

    def register_many(self, mapping):
        """
        Register multiple items.

        Args:
            mapping (dict[str, dict] | Iterable[tuple[str, dict]]):
                Keys map to item dicts (same schema as :meth:`register`).
        """
        iterable = mapping.items() if hasattr(mapping, "items") else mapping
        for k, meta in iterable:
            self.register(k, **meta)

    def keys(self):
        """Returns:
            KeysView[str]: All registered keys.
        """
        return self._registry.keys()

    def __contains__(self, key):
        return key in self._registry

    def __len__(self):
        return len(self._registry)

    def info(self, key):
        """Return the registered metadata (by reference).

        Args:
            key (str): Registered key.

        Returns:
            dict: The item’s metadata dictionary.

        Raises:
            KeyError: If the key is unknown.
        """
        return self._registry[key]

    # ---- download / caching

    def grab(self, key: str, *, fname=None,
             require_hash: bool = False, allow_mirror_fallback: bool = True):
        """
        Ensure the file for ``key`` is cached locally and return its path.

        Args:
            key (str): Registered key.
            fname (str | None): Override cache filename (defaults to item's ``fname``).
            require_hash (bool): If True, require sha256/sha512 on the item; else ValueError.
            allow_mirror_fallback (bool): If True, try mirrors/IPFS if the primary URL fails.

        Returns:
            str: Local filesystem path of the cached file.

        Raises:
            KeyError: If ``key`` is unknown.
            ValueError: If ``require_hash=True`` but no supported hash is present.
            Exception: Propagates the last download exception if all sources fail.
        """
        if key not in self._registry:
            raise KeyError(f"Unknown key={key!r}. Valid keys: {sorted(self._registry)}")

        item = self._registry[key]
        url = item["url"]
        mirrors = list(item.get("mirrors", []))

        # Expand IPFS CIDs into gateway URLs:contentReference[oaicite:4]{index=4}
        for cid in item.get("ipfs_cids", []):
            for gw in self.ipfs_gateways:
                mirrors.append(f"{gw}/{cid}")

        # Build grabdata kwargs with optional hash verification:contentReference[oaicite:5]{index=5}
        grabkw = {"appname": self.appname}
        if fname is None:
            fname = item.get("fname", None)
        if fname:
            grabkw["fname"] = fname

        selected_hasher = None
        for hasher in self.hasher_priority:
            if hasher in item:
                selected_hasher = hasher
                grabkw.update({"hash_prefix": item[hasher], "hasher": hasher})
                break

        if require_hash and selected_hasher is None:
            raise ValueError(
                f"Item {key!r} has no supported hash; set sha256/sha512 or disable require_hash."
            )

        # Primary URL then mirror fallback:contentReference[oaicite:6]{index=6}
        try:
            return ub.grabdata(url, **grabkw)
        except Exception as main_ex:
            if not allow_mirror_fallback or not mirrors:
                raise
            last_ex = main_ex
            for m in mirrors:
                try:
                    return ub.grabdata(m, **grabkw)
                except Exception as ex:
                    last_ex = ex
                    continue
            raise last_ex

    def update_hashes(
        self,
        keys=None,
        hasher_priority=("sha256", "sha512"),
        request_hashers=("sha256", "sha512"),
        require_existing_hash: bool = False,
        ensure_ipfs: bool = False,
        ensure_metadata: bool = False,
        metadata_func=None,
    ) -> dict[str, dict]:
        """
        Download items and (re)compute requested hashes; optionally attach IPFS CIDs
        and/or metadata. Returns a **new** mapping with updated entries.

        This is a cleaned, keyword-driven port of the original helper that updated
        hashes and optionally added IPFS pins and basic metadata:contentReference[oaicite:7]{index=7}.

        Args:
            keys (list[str] | None): If given, only update these keys (default: all).
            hasher_priority (tuple[str, ...]): Order to *use* for verification when
                ``require_existing_hash=True`` (e.g., prefer sha256):contentReference[oaicite:8]{index=8}.
            request_hashers (tuple[str, ...]): Hashers to compute (and store) if
                absent (e.g., ('sha256','sha512')).
            require_existing_hash (bool): If True, only download items that already
                have one of the hashes in ``hasher_priority``; use it to verify.
            ensure_ipfs (bool): If True, add files to IPFS via ``ipfs add`` and store
                resulting CIDs (requires IPFS CLI):contentReference[oaicite:9]{index=9}.
            ensure_metadata (bool): If True, call ``metadata_func(fpath, item)`` and
                store the returned dict into ``item['properties']``.
            metadata_func (callable | None): Callable that accepts (fpath, item)
                and returns a dict of metadata to persist.

        Returns:
            dict[str, dict]: A new mapping of updated items.

        Example:
            >>> # xdoctest: +REQUIRES(--network)
            >>> reg = DemoDataRegistry(appname='ubelt/demodata')
            >>> reg.register(
            ...     key='airport',
            ...     url=('https://upload.wikimedia.org/wikipedia/commons/9/9e/'
            ...          'Beijing_Capital_International_Airport_on_18_February_2018_-_SkySat_%281%29.jpg'),
            ...     fname='airport.jpg',
            ... )
            >>> updated = update_hashes(reg, request_hashers=('sha256',), ensure_ipfs=False)
            >>> assert 'sha256' in updated['airport']
        """
        # Create a deep-ish copy so we don’t mutate the live registry directly.
        updated = {k: dict(v) for k, v in self._registry.items()}
        target_keys = keys if keys is not None else list(updated.keys())

        for key in target_keys:
            if key not in updated:
                raise KeyError(f"Unknown key {key!r}")

            item = updated[key]
            grabkw = {"appname": self.appname}

            # If we want to require an existing hash, set up verification.
            if require_existing_hash:
                selected_hasher = None
                for hasher in hasher_priority:
                    if hasher in item:
                        selected_hasher = hasher
                        grabkw.update({"hash_prefix": item[hasher], "hasher": hasher})
                        break
                if selected_hasher is None:
                    # Skip items with no prior hash (or raise if preferred)
                    continue

            # Choose a deterministic filename if provided
            if "fname" in item:
                grabkw["fname"] = item["fname"]

            # Try the primary and mirrors (reuse the same fallback pattern):contentReference[oaicite:10]{index=10}
            url = item["url"]
            mirrors = list(item.get("mirrors", []))

            # Expand IPFS cids into gateways:contentReference[oaicite:11]{index=11}
            for cid in item.get("ipfs_cids", []):
                for gw in self.ipfs_gateways:
                    mirrors.append(f"{gw}/{cid}")

            try:
                fpath = _grab_with_mirrors(url, mirrors, grabkw)
            except Exception:
                # If download fails here, bubble up (or choose to skip).
                raise

            # Compute/requested hashes if missing
            for hasher in request_hashers:
                if hasher not in item:
                    item[hasher] = ub.hash_file(fpath, hasher=hasher)
            # Normalize ordering (optional cosmetic step)
            for hasher in request_hashers:
                item[hasher] = item.pop(hasher)

            if ensure_metadata and callable(metadata_func):
                try:
                    props = metadata_func(fpath, item) or {}
                    if props:
                        item["properties"] = props
                except Exception as ex:
                    # Non-fatal; leave a breadcrumb in case helpful.
                    item.setdefault("properties", {})
                    item["properties"]["_metadata_error"] = str(ex)

            if ensure_ipfs:
                # Add to IPFS and store CID. Requires 'ipfs' CLI to be available.
                info = ub.cmd(f'ipfs add "{fpath}" --progress --cid-version=1')
                # Parse CID (expected format: "<hash> <cid> <name>" or similar)
                try:
                    # Heuristic: last line contains the CID after a space.
                    cid = info["out"].strip().split()[-2]
                    item.setdefault("ipfs_cids", [])
                    if cid not in item["ipfs_cids"]:
                        item["ipfs_cids"].append(cid)
                except Exception:
                    # If we can’t parse, embed raw stdout for debugging.
                    item.setdefault("ipfs_cids", [])
                    item["ipfs_cids"].append(info["out"].strip())

        return updated


def _grab_with_mirrors(url, mirrors, grabkw):
    """
    Try primary URL first, then mirrors in order (utility function):contentReference[oaicite:12]{index=12}.
    """
    try:
        return ub.grabdata(url, **grabkw)
    except Exception as main_ex:
        last_ex = main_ex
        for m in mirrors:
            try:
                return ub.grabdata(m, **grabkw)
            except Exception as ex:
                last_ex = ex
                continue
        raise last_ex
