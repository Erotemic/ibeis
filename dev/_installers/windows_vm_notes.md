
# List all the VMS
virsh list --all

# List the snapshots of the win11-fresh VM
virsh snapshot-list win11-fresh
virsh snapshot-list win11-fresh --tree

# Restore a fresh snapshot
virsh snapshot-revert win11-fresh Fresh-System





### Migrating To A Better Snapshot System:


# Checks

```bash
virsh domstate win11-fresh
virsh snapshot-current win11-fresh --name
virsh domblklist win11-fresh --details

STAMP=$(date +%Y%m%d-%H%M%S)
virsh dumpxml win11-fresh > ~/win11-fresh.$STAMP.xml
echo ~/win11-fresh.$STAMP.xml



### FLatten

SRC=/data/service/vms/libvirt/images/win11-fresh.qcow2
ROOT=/media/joncrall/flash1/vms/win11-fresh
BASE=$ROOT/bases/Fresh-System.raw
WORK=$ROOT/win11-fresh.qcow2

qemu-img info "$SRC"
df -h "$ROOT" 2>/dev/null || df -h /media/joncrall/flash1


### create the destination and convert

sudo install -d -m 0755 "$ROOT/bases"

sudo qemu-img convert -p \
    -f qcow2 \
    -O raw \
    "$SRC" \
    "$BASE.tmp"

```

The migration takes some time, after


```bash
sudo mv "$BASE.tmp" "$BASE"
sudo chown libvirt-qemu:kvm "$BASE"
sudo chmod 0440 "$BASE"

qemu-img info "$BASE"
ls -lh "$BASE"
du -h "$BASE"


# Then create the disposable working overlay:
cd "$ROOT"

sudo qemu-img create \
    -f qcow2 \
    -o compat=1.1,preallocation=metadata,lazy_refcounts=on \
    -F raw \
    -b bases/Fresh-System.raw \
    win11-fresh.qcow2

sudo chown libvirt-qemu:kvm win11-fresh.qcow2
sudo chmod 0660 win11-fresh.qcow2

qemu-img info --backing-chain win11-fresh.qcow2
```

