# Background Task Schedules

This document provides an overview of the scheduled background tasks in the cluster, primarily focusing on data backups, synchronization, and cleanup jobs.

## Overview

The cluster utilizes several automated mechanisms (mostly `CronJobs` and Kopiur `SnapshotSchedule`s) to maintain data integrity and cleanup old data. Many of these have been synchronized to run during off-peak hours (e.g., 4:00 AM) to minimize load on cluster resources, but they can be adjusted as needed.

## Backup Schedules

All critical backup schedules are tagged with `# [BACKUP_SCHEDULE]` in their respective YAML configurations so they can be easily identified and searched.

### Kopiur (Volume Backups)

Kopiur (Kopia) backs up persistent volumes across various applications. The base configurations are located in `kubernetes/components/kopiur/`.

- **Local tier (`backup/`)**: A `SnapshotSchedule` on `0 0,12 * * *` writing to the local Kopia repository on the NAS.
- **Remote tier (`remote/`)**: A `SnapshotSchedule` on `0 2,14 * * *` copying offsite to Cloudflare R2.

Applications opt in to these schedules by injecting the Kopiur components into their `ks.yaml`.

### Database Backups

- **CloudNativePG (`kubernetes/apps/database/cloudnative-pg/backup/helmrelease.yaml`)**:
  Performs full PostgreSQL cluster backups to an NFS NAS share.

## Maintenance and Cleanup Schedules

In addition to backups, several applications have their own internal scheduled tasks:

- **Recyclarr**: Syncs Trash Guides to Radarr/Sonarr instances.
- **YTDL-Sub**: Downloads subscribed YouTube channels periodically.
- **Kometa (Plex Meta Manager)**: Updates Plex collections, overlays, and metadata.
- **Plex Image Cleanup**: Cleans up unused images from the Plex config directory.

## Finding and Modifying Schedules

If you need to modify or review the backup schedules, you can easily search the repository for the tag:

```bash
grep -r "# [BACKUP_SCHEDULE]" kubernetes/
```

To modify a schedule, simply update the cron expression string next to the tag in the relevant file.
