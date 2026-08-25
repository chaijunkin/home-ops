# Troubleshooting Kopiur Permission Errors with `local-hostpath`

When running Kopiur (or any Kopia-based backup solution) as an unprivileged user against PVCs provisioned by `democratic-csi` with the `local-hostpath` driver, you may encounter `permission denied` errors on seemingly random files, even when your `KOPIUR_PUID`, `KOPIUR_PGID`, and `fsGroup` correctly match the application's identities.

## The Symptoms
- The backup succeeds for 99% of files, but fails on a small subset (usually 1–300 files).
- The failed files are typically:
  - Internal application caches (e.g., Plex `.bundle` directories or `Metadata`).
  - Temporary processing files (e.g., Calibre `.zip.*` conversion files).
  - Rapidly changing state files or exclusive locks.
- Checking the live PVC shows that the files either no longer exist, or they exist with correct ownership (e.g., `drwxrwsr-x 2000 2000`) but still triggered a read error.

## The Root Cause: `democratic-csi local-hostpath` Limitations

The issue stems from how `democratic-csi` fakes a `VolumeSnapshot` for standard `ext4` host directories.

1. **Lack of Native Atomic Snapshots**: 
   True CSI volume snapshots rely on the underlying filesystem (like ZFS or BTRFS) to instantly freeze a perfect, atomic, read-only state of the disk at a specific millisecond. `local-hostpath` does not support this.
2. **Live File Copying**: 
   To simulate a snapshot, the `democratic-csi` driver performs a live file-copy (like `rsync` or `cp -a`) of your application's data folder into a new "snapshot" clone folder. 
3. **Mid-Write Inconsistencies**: 
   Because your applications are actively running during this copy, they are constantly creating, locking, and deleting temporary files. If the CSI driver copies a folder structure but an underlying temporary file is exclusively locked, or deleted mid-copy, the resulting clone ends up with corrupted permissions, phantom files, or mismatched access bits.
4. **Kopia Hits the Wall**:
   When Kopiur subsequently runs against this flawed clone as an unprivileged user, the strict POSIX permissions block access to these half-copied or locked files, resulting in `permission denied`.

## The Solutions

### Solution 1: Use the Root Mover (Pragmatic Fix)
By instructing Kopiur to run the backup mover as `root`, it can brute-force read access through any mismatched POSIX permissions or phantom locks left behind by the flawed copy process.

**Implementation**:
In the application's `ks.yaml`, inject the root variables:
```yaml
    substitute:
      KOPIUR_PUID: "0"
      KOPIUR_PGID: "0"
      KOPIUR_NONROOT: "false"
```
*(This is the easiest fix and is currently implemented for your failing apps).*

### Solution 2: Ignore the Noise
Since the failing files are inherently temporary caches and metadata bundles that aren't critical for disaster recovery, you can instruct Kopiur to simply skip them.

**Implementation**:
In the application's `SnapshotPolicy`, define `ignoreRules`:
```yaml
  files:
    ignoreRules:
      - ".bundle"
      - "thumbnails"
      - "Metadata"
      - "*.tmp"
```

### Solution 3: Migrate to Atomic Storage
To achieve perfect, error-free backups without skipping files or running as root, the underlying storage class must support true atomic snapshots. 
- **Recommendation**: Migrate the PVCs from `local-hostpath` to a storage driver that supports native freezing (e.g., `zfs-localpv`, `mayastor`, or using `democratic-csi` with actual ZFS datasets).
