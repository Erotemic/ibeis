

# Restore a fresh snapshot
virsh list --all
virsh snapshot-list win11-fresh
virsh snapshot-revert win11-fresh Fresh-System

