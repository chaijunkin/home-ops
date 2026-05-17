# Background Task Schedules

This document provides an overview of the scheduled background tasks in the cluster, primarily focusing on data backups, synchronization, and cleanup jobs.

## Overview

The cluster utilizes several automated mechanisms (mostly `CronJobs` and VolSync `ReplicationSources`) to maintain data integrity and cleanup old data. Many of these have been synchronized to run during off-peak hours (e.g., 4:00 AM) to minimize load on cluster resources, but they can be adjusted as needed.

## Backup Schedules

All critical backup schedules are tagged with `# [BACKUP_SCHEDULE]` in their respective YAML configurations so they can be easily identified and searched.

### VolSync (Volume Backups)

VolSync is used to back up persistent volumes across various applications. The base configurations are located in `kubernetes/components/volsync/`. 

- **Kopia (`kopia.yaml`)**: Handles local backups to an NFS NAS.
- **R2 (`r2.yaml`)**: Handles offsite backups to Cloudflare R2.

These components define a `ReplicationSource` which contains a `schedule` field. Applications opt-in to these schedules by using the VolSync Kustomize components.

### Database Backups

- **CloudNativePG (`kubernetes/apps/database/cloudnative-pg/backup/helmrelease.yaml`)**:
  Performs full PostgreSQL cluster backups to an NFS NAS share.

## Maintenance and Cleanup Schedules

In addition to backups, several applications have their own internal scheduled tasks:

- **Recyclarr**: Syncs Trash Guides to Radarr/Sonarr instances.
- **YTDL-Sub**: Downloads subscribed YouTube channels periodically.
- **Kometa (Plex Meta Manager)**: Updates Plex collections, overlays, and metadata.
- **Plex Image Cleanup**: Cleans up unused images from the Plex config directory.
- **Remediation Job**: A custom cronjob that runs periodically to detect and unlock stuck Restic locks from failed VolSync backup attempts.

## Finding and Modifying Schedules

If you need to modify or review the backup schedules, you can easily search the repository for the tag:

```bash
grep -r "# [BACKUP_SCHEDULE]" kubernetes/
```

To modify a schedule, simply update the cron expression string next to the tag in the relevant file.
