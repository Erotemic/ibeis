
VM Share directory on linux: `/srv/vmshare`

VM Share network location on windows: `\\192.168.122.1\vmshare`, user and pass are just the username.


Snapshot helpers without checks:

```
# Restore Fresh System
ROOT=/media/joncrall/flash1/vms/win11-fresh
WORK=$ROOT/win11-fresh.qcow2

virsh shutdown win11-fresh

while [ "$(virsh domstate win11-fresh)" != "shut off" ]; do
    sleep 1
done

sudo rm -f "$WORK"

cd "$ROOT"

sudo qemu-img create \
    -f qcow2 \
    -o compat=1.1,lazy_refcounts=on \
    -F raw \
    -b bases/Fresh-System.raw \
    win11-fresh.qcow2

sudo chown libvirt-qemu:kvm "$WORK"
sudo chmod 0660 "$WORK"

virsh start win11-fresh
```


```bash
# Overwrite Fresh System
ROOT=/media/joncrall/flash1/vms/win11-fresh
WORK=$ROOT/win11-fresh.qcow2
BASE=$ROOT/bases/Fresh-System.raw
NEWBASE=$ROOT/bases/Fresh-System.new.raw

sudo qemu-img convert -p -f qcow2 -O raw "$WORK" "$NEWBASE"
sudo chown libvirt-qemu:kvm "$NEWBASE"
sudo chmod 0440 "$NEWBASE"
sudo mv "$NEWBASE" "$BASE"
```


New snapshot helpers with checks:


```bash
win11_snapshot() {
    local name="${1:?usage: win11_snapshot SNAPSHOT_NAME}"
    local vm="win11-fresh"
    local root="/media/joncrall/flash1/vms/win11-fresh"
    local work="$root/win11-fresh.qcow2"
    local base="$root/bases/$name.raw"
    local tmp="$base.tmp.$$"
    local state

    [[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || {
        echo "Invalid snapshot name: $name" >&2
        return 2
    }

    state=$(virsh domstate "$vm") || return
    [[ "$state" == "shut off" ]] || {
        echo "$vm must be fully shut off; current state: $state" >&2
        return 1
    }

    [[ -e "$work" ]] || {
        echo "Working image does not exist: $work" >&2
        return 1
    }

    [[ ! -e "$base" ]] || {
        echo "Snapshot already exists: $base" >&2
        return 1
    }

    echo "Creating snapshot: $name"
    if ! sudo qemu-img convert -p \
        -f qcow2 \
        -O raw \
        "$work" \
        "$tmp"
    then
        sudo rm -f "$tmp"
        return 1
    fi

    sudo chown libvirt-qemu:kvm "$tmp"
    sudo chmod 0440 "$tmp"
    sudo mv "$tmp" "$base"

    echo "Created: $base"
    sudo qemu-img info "$base"
}


win11_restore() {
    local name="${1:?usage: win11_restore SNAPSHOT_NAME}"
    local vm="win11-fresh"
    local root="/media/joncrall/flash1/vms/win11-fresh"
    local work="$root/win11-fresh.qcow2"
    local base="$root/bases/$name.raw"
    local tmp="$root/.win11-fresh.qcow2.tmp.$$"
    local state

    [[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || {
        echo "Invalid snapshot name: $name" >&2
        return 2
    }

    state=$(virsh domstate "$vm") || return
    [[ "$state" == "shut off" ]] || {
        echo "$vm must be fully shut off; current state: $state" >&2
        return 1
    }

    [[ -r "$base" ]] || {
        echo "Snapshot does not exist: $base" >&2
        return 1
    }

    sudo rm -f "$tmp"

    if ! sudo qemu-img create \
        -f qcow2 \
        -o compat=1.1,lazy_refcounts=on \
        -F raw \
        -b "bases/$name.raw" \
        "$tmp"
    then
        sudo rm -f "$tmp"
        return 1
    fi

    sudo chown libvirt-qemu:kvm "$tmp"
    sudo chmod 0660 "$tmp"

    # Atomic replacement on the same filesystem. The old working state
    # disappears here; the immutable named base is untouched.
    sudo mv -f "$tmp" "$work"

    echo "Restored: $name"
    sudo -u libvirt-qemu qemu-img info --backing-chain "$work"
}
```



-----

# Migrating To A Better VM Snapshot System

Above this is the instructions after this migration happend.


The old `win11-fresh` setup used an internal qcow2 snapshot on `/data`. Restoring it required `qemu-img snapshot -a` against a large qcow2 on HDD-backed ZFS and could take hours.

The replacement uses:

```text
Fresh-System.raw      # immutable base
win11-fresh.qcow2     # disposable writable overlay
```

The base lives on `flash1` NVMe. Resetting the VM only requires recreating the small overlay.

## Check Current State

The VM should be shut down and the desired snapshot should be current.

```bash
virsh domstate win11-fresh
virsh snapshot-current win11-fresh --name
virsh domblklist win11-fresh --details

STAMP=$(date +%Y%m%d-%H%M%S)
virsh dumpxml win11-fresh > ~/win11-fresh.$STAMP.xml
echo ~/win11-fresh.$STAMP.xml
```

## Flatten The Snapshot

```bash
SRC=/data/service/vms/libvirt/images/win11-fresh.qcow2
ROOT=/media/joncrall/flash1/vms/win11-fresh
BASE=$ROOT/bases/Fresh-System.raw
WORK=$ROOT/win11-fresh.qcow2

qemu-img info "$SRC"
df -h "$ROOT" 2>/dev/null || df -h /media/joncrall/flash1

sudo install -d -m 0755 "$ROOT/bases"

sudo qemu-img convert -p \
    -f qcow2 \
    -O raw \
    "$SRC" \
    "$BASE.tmp"
```

The conversion can take some time. After it finishes:

```bash
sudo mv "$BASE.tmp" "$BASE"
sudo chown libvirt-qemu:kvm "$BASE"
sudo chmod 0440 "$BASE"

qemu-img info "$BASE"
ls -lh "$BASE"
du -h "$BASE"
```

## Create The Disposable Overlay

`libvirt-qemu` needs traverse permission through `/media/joncrall`:

```bash
sudo setfacl -m u:libvirt-qemu:x /media/joncrall
```

Create the working overlay:

```bash
cd "$ROOT"

sudo qemu-img create \
    -f qcow2 \
    -o compat=1.1,lazy_refcounts=on \
    -F raw \
    -b bases/Fresh-System.raw \
    win11-fresh.qcow2

sudo chown libvirt-qemu:kvm win11-fresh.qcow2
sudo chmod 0660 win11-fresh.qcow2
```

Verify the backing chain and permissions:

```bash
sudo qemu-img info --backing-chain "$WORK"

namei -l "$WORK"

sudo -u libvirt-qemu qemu-img info --backing-chain "$WORK"
```

The chain should be:

```text
win11-fresh.qcow2
└── bases/Fresh-System.raw
```

## Change The VM Disk Source

Use the XML backup created earlier:

```bash
OLD_XML=~/win11-fresh.<timestamp>.xml
NEW_XML=/tmp/win11-fresh-flash1.xml

cp "$OLD_XML" "$NEW_XML"

sed -i \
    "s|/data/service/vms/libvirt/images/win11-fresh.qcow2|$WORK|" \
    "$NEW_XML"

diff -u "$OLD_XML" "$NEW_XML"
```

The diff should only change the `vda` source path.

```bash
virsh define "$NEW_XML"
virsh domblklist win11-fresh --details
```

Start and verify the VM:

```bash
virsh start win11-fresh
virsh domstate win11-fresh
```

Keep the old qcow2 and XML backup until Windows has booted successfully from the new disk chain.

## Remove Old Snapshot Metadata

After verifying the new VM:

```bash
virsh snapshot-delete win11-fresh Fresh-System --metadata
virsh snapshot-list win11-fresh
```

Do not use `virsh snapshot-revert` for this VM after migration.

## Reset To Fresh-System

Shut the VM down:

```bash
virsh shutdown win11-fresh
virsh domstate win11-fresh
```

Once it reports `shut off`:

```bash
ROOT=/media/joncrall/flash1/vms/win11-fresh
WORK=$ROOT/win11-fresh.qcow2

sudo rm "$WORK"

cd "$ROOT"

sudo qemu-img create \
    -f qcow2 \
    -o compat=1.1,lazy_refcounts=on \
    -F raw \
    -b bases/Fresh-System.raw \
    win11-fresh.qcow2

sudo chown libvirt-qemu:kvm win11-fresh.qcow2
sudo chmod 0660 win11-fresh.qcow2

virsh start win11-fresh
```

Resetting now discards the writable overlay and creates a new one backed by the immutable `Fresh-System.raw`.


# Old VERY SLOW snapshot system

# List all the VMS
virsh list --all

# List the snapshots of the win11-fresh VM
virsh snapshot-list win11-fresh
virsh snapshot-list win11-fresh --tree

# Restore a fresh snapshot
virsh snapshot-revert win11-fresh Fresh-System

Migrated to the above


